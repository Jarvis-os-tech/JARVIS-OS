"""Local project documents, with confined paths, atomic metadata and recoverable changes."""
from __future__ import annotations

import hashlib
import io
import json
import mimetypes
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import threading
from datetime import datetime, timezone
from uuid import uuid4

from .config import ROOT

MAX_FILE = 20 * 1024 * 1024
MAX_TEXT = 256 * 1024
TEXT_EXTENSIONS = {'.txt', '.md', '.json', '.csv', '.html', '.css', '.js', '.py', '.yaml', '.yml', '.xml', '.svg', '.log', '.ini', '.toml', '.sh', '.sql'}
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}
KINDS = {'idea', 'note', 'decision', 'task', 'image', 'file'}
PANEL_DEFAULTS = {
    'brief': {'x':53.8,'y':2.6,'w':18.5,'h':15.5},
    'files': {'x':10.7,'y':9.9,'w':15,'h':26.5},
    'ideas': {'x':10.1,'y':55.5,'w':15.6,'h':40},
    'plan': {'x':64.7,'y':21.1,'w':27.5,'h':71.8},
    'tasks': {'x':37.5,'y':85,'w':14.6,'h':14.5},
}


class WorkspaceError(ValueError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-f0-9]{32}', value):
        raise WorkspaceError('Invalid project or item identifier.')
    return value


def text(value, maximum=8000, blank=True):
    if not isinstance(value, str) or len(value) > maximum or (not blank and not value.strip()):
        raise WorkspaceError(f'Enter text of at most {maximum} characters.')
    return value


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f'.{path.name}.{uuid4().hex}.tmp')
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


class ProjectStore:
    def __init__(self, root):
        self.root = Path(root)
        self.lock = threading.RLock()
        self.view = None

    def directory(self, project_id):
        path = self.root / identifier(project_id)
        if path.is_symlink():
            raise WorkspaceError('Linked project directories are not supported.')
        return path

    def project(self, project_id):
        try:
            path = self.directory(project_id) / 'project.json'
            if path.is_symlink():
                raise WorkspaceError('Linked metadata is not supported.')
            return json.loads(path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            raise WorkspaceError('Project not found.') from None

    def save(self, project):
        project['revision'] += 1
        project['updated_at'] = now()
        atomic_json(self.directory(project['id']) / 'project.json', project)

    def active(self):
        with self.lock:
            try:
                return json.loads((self.root / 'workspace.json').read_text())['active_id']
            except FileNotFoundError:
                return None

    def activate(self, project_id):
        if project_id is not None:
            self.project(project_id)
        atomic_json(self.root / 'workspace.json', {'active_id': project_id})
        self.view = None

    def projects(self):
        result = []
        for path in self.root.glob('*/project.json'):
            if path.parent.is_symlink() or path.is_symlink():
                continue
            p = self.project(path.parent.name)
            result.append({k: p[k] for k in ('id', 'name', 'brief', 'archived', 'updated_at', 'revision')})
        return sorted(result, key=lambda p: p['updated_at'], reverse=True)

    def path(self, project_id, value, *, root_ok=False):
        self.project(project_id)
        value = text(value, 512)
        if not value and root_ok:
            parts = ()
        else:
            parts = PurePosixPath(value).parts
            if not parts or value.startswith('/') or '\\' in value or any(part in {'.', '..'} or part.startswith('.') for part in parts) or any(ord(c) < 32 for c in value):
                raise WorkspaceError('Use a relative project path without hidden folders or .. segments.')
        base = self.directory(project_id) / 'files'
        candidate = base
        if base.is_symlink():
            raise WorkspaceError('Linked folders are not supported.')
        for part in parts:
            candidate /= part
            if candidate.is_symlink():
                raise WorkspaceError('Linked files and folders are not supported.')
        if not candidate.resolve().is_relative_to(base.resolve()):
            raise WorkspaceError('Path must stay inside the project.')
        return candidate

    def files(self, project_id):
        base = self.path(project_id, '', root_ok=True)
        result = []
        for directory, dirs, files in os.walk(base, followlinks=False):
            dirs[:] = sorted(d for d in dirs if not d.startswith('.') and not (Path(directory) / d).is_symlink())
            for name in dirs + sorted(files):
                path = Path(directory) / name
                if name.startswith('.') or path.is_symlink():
                    continue
                folder = path.is_dir()
                result.append({'path': path.relative_to(base).as_posix(), 'name': name, 'folder': folder,
                               'size': 0 if folder else path.stat().st_size,
                               'image': not folder and path.suffix.lower() in IMAGE_EXTENSIONS})
                if len(result) > 2000:
                    raise WorkspaceError('Project exceeds the 2,000 item display limit.')
        return result

    def snapshot(self):
        with self.lock:
            active = self.active()
            project = self.project(active) if active else None
            return {'projects': self.projects(), 'active_id': active, 'project': project,
                    'files': self.files(active) if active else [], 'view': self.view}

    def context(self):
        with self.lock:
            active = self.active()
            if not active:
                return json.dumps({'active_project': None, 'projects': self.projects()[:30]})
            p = self.project(active)
            return json.dumps({'active_project': {k: p[k] for k in ('id', 'name', 'brief', 'summary')},
                               'initial_demo_image': p.get('initial_demo_image'),
                               'cad': {k: p.get('cad', {}).get(k) for k in ('status', 'message', 'design_path', 'current', 'missing_measurements')},
                               'saved_cards': p['cards'][-20:], 'files': self.files(active)[:60]}, ensure_ascii=False)[:22000]

    def file_revision(self, path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def read_file(self, project_id, path, offset=0, limit=16000):
        target = self.path(project_id, path)
        if not target.is_file():
            raise WorkspaceError('File not found.')
        if target.stat().st_size > MAX_FILE:
            raise WorkspaceError('File exceeds the 20 MB limit.')
        data = target.read_bytes()
        result = {'path': path, 'revision': hashlib.sha256(data).hexdigest(), 'size': len(data), 'editable': False}
        if target.suffix.lower() == '.pdf':
            from pypdf import PdfReader
            try:
                reader = PdfReader(io.BytesIO(data))
                if reader.is_encrypted:
                    raise WorkspaceError('This PDF is encrypted. Upload an unlocked copy.')
                extracted = []
                for page in reader.pages[:50]:
                    extracted.append((page.extract_text() or '')[:16000])
                    if sum(map(len, extracted)) >= MAX_TEXT:
                        break
                body = '\n\n'.join(extracted)[:MAX_TEXT]
                result['notice'] = 'Text from up to 50 pages; scanned pages need a text-based PDF.'
            except WorkspaceError:
                raise
            except Exception:
                raise WorkspaceError('Could not extract text from this PDF. You can still download it.') from None
        elif target.suffix.lower() in IMAGE_EXTENSIONS:
            return {**result, 'image': True, 'notice': 'Image preview is on the board. Use inspect_image to see its contents.'}
        else:
            try:
                body = data.decode('utf-8')
                if '\x00' in body:
                    raise UnicodeError()
                result['editable'] = len(data) <= MAX_TEXT
            except UnicodeError:
                return {**result, 'notice': 'Binary file. Available for download.'}
        if not isinstance(offset, int) or not isinstance(limit, int) or offset < 0 or not 1 <= limit <= MAX_TEXT:
            raise WorkspaceError('Invalid text range.')
        return {**result, 'content': body[offset:offset + limit], 'offset': offset, 'total': len(body),
                'truncated': offset + limit < len(body)}

    def history(self, project_id, path, source):
        version = uuid4().hex
        base = self.directory(project_id) / 'versions' / version
        base.mkdir(parents=True)
        shutil.copyfile(source, base / 'content')
        atomic_json(base / 'entry.json', {'id': version, 'path': path, 'created_at': now()})
        return version

    def put(self, project_id, path, data, expected_revision=None):
        if len(data) > MAX_FILE:
            raise WorkspaceError('Files must be no larger than 20 MB.')
        target = self.path(project_id, path)
        if target.exists():
            if not target.is_file():
                raise WorkspaceError('A folder already uses that name.')
            if not expected_revision or expected_revision != self.file_revision(target):
                raise WorkspaceError('This file already exists or changed. Read it again before replacing it.')
            self.history(project_id, path, target)
        elif expected_revision:
            raise WorkspaceError('This file was moved or deleted. Reopen the project before saving.')
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name('.' + uuid4().hex + '.tmp')
        try:
            temporary.write_bytes(data)
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
        p = self.project(project_id)
        self.save(p)
        return {'path': path, 'revision': hashlib.sha256(data).hexdigest(), 'saved': True}

    def upload(self, project_id, path, data):
        with self.lock:
            suffix = PurePosixPath(path).suffix.lower()
            if suffix in IMAGE_EXTENSIONS:
                from PIL import Image
                try:
                    with Image.open(io.BytesIO(data)) as im:
                        if im.width * im.height > 25_000_000 or im.format not in {'PNG', 'JPEG', 'WEBP'}:
                            raise ValueError()
                        im.verify()
                except Exception:
                    raise WorkspaceError('Choose a valid PNG, JPEG or WebP image under 25 megapixels.') from None
            result = self.put(project_id, path, data)
            if suffix in IMAGE_EXTENSIONS:
                self.execute('save_card', {'project_id': project_id, 'kind': 'image', 'title': PurePosixPath(path).stem, 'body': '', 'path': path})
            return result

    def image_part(self, project_id, path):
        from PIL import Image
        target = self.path(project_id, path)
        if target.suffix.lower() not in IMAGE_EXTENSIONS or not target.is_file():
            raise WorkspaceError('Choose an uploaded PNG, JPEG or WebP image.')
        with Image.open(target) as im:
            if im.width * im.height > 25_000_000:
                raise WorkspaceError('Image is too large.')
            im.thumbnail((1280, 1280))
            output = io.BytesIO()
            im.convert('RGB').save(output, format='JPEG', quality=85)
        return output.getvalue()

    def execute(self, name, a):
        with self.lock:
            return self._execute(name, a)

    def _execute(self, name, a):
        if name == 'list_projects':
            return {'projects': self.projects(), 'active_id': self.active()}
        if name == 'create_project':
            p = {'id': uuid4().hex, 'name': text(a['name'], 100, False).strip(), 'brief': text(a.get('brief', '')),
                 'summary': '', 'archived': False, 'created_at': now(), 'updated_at': now(), 'revision': 0,
                 'cards': [], 'layout': {},
                 'initial_demo_image': {'status': 'waiting_for_plan' if a.get('auto_demo_image', True) else 'disabled'}}
            (self.directory(p['id']) / 'files').mkdir(parents=True)
            self.save(p)
            self.activate(p['id'])
            return p
        pid = identifier(a['project_id'])
        p = self.project(pid)
        if name == 'get_project':
            return {'project': p, 'files': self.files(pid)}
        if name == 'open_project':
            if p['archived']:
                p['archived'] = False
                self.save(p)
            self.activate(pid)
            return {'project': p, 'files': self.files(pid)}
        if name == 'close_project':
            if self.active() != pid:
                raise WorkspaceError('That project is not open.')
            self.activate(None)
            return {'closed': pid, 'saved': True}
        if name == 'update_project':
            for key, maximum in [('name', 100), ('brief', 8000), ('summary', 12000)]:
                if key in a:
                    p[key] = text(a[key], maximum, key != 'name')
            if 'archived' in a:
                if not isinstance(a['archived'], bool):
                    raise WorkspaceError('Archived must be true or false.')
                p['archived'] = a['archived']
                if p['archived'] and self.active() == pid:
                    self.activate(None)
            self.save(p)
            return p
        if name == 'list_files':
            query = text(a.get('query', ''), 200).casefold()
            return {'files': [f for f in self.files(pid) if query in f['path'].casefold()]}
        if name == 'read_file':
            return self.read_file(pid, a['path'], a.get('offset', 0), a.get('limit', 16000))
        if name in {'write_file', 'edit_file'}:
            if name == 'edit_file':
                old = self.read_file(pid, a['path'], limit=MAX_TEXT)
                if not old['editable']:
                    raise WorkspaceError('Only UTF-8 text files up to 256 KB can be edited.')
                needle = text(a['old_text'], MAX_TEXT, False)
                if old['content'].count(needle) != 1:
                    raise WorkspaceError('The text to replace must occur exactly once.')
                body = old['content'].replace(needle, text(a['new_text'], MAX_TEXT), 1)
            else:
                body = text(a['content'], MAX_TEXT)
            data = body.encode('utf-8')
            if len(data) > MAX_TEXT:
                raise WorkspaceError('Text files must be at most 256 KB.')
            if PurePosixPath(a['path']).suffix.lower() in IMAGE_EXTENSIONS | {'.pdf'}:
                raise WorkspaceError('Use a text filename for text content.')
            return self.put(pid, a['path'], data, a.get('expected_revision'))
        if name == 'create_folder':
            target = self.path(pid, a['path'])
            if target.exists():
                raise WorkspaceError('That path already exists.')
            target.mkdir(parents=True)
            self.save(p)
            return {'path': a['path'], 'created': True}
        if name in {'move_file', 'copy_file', 'delete_file'}:
            source = self.path(pid, a['path'])
            if not source.exists():
                raise WorkspaceError('File or folder not found.')
            # Reject links anywhere in a subtree before copying or moving it.
            if source.is_dir() and any(item.is_symlink() for item in source.rglob('*')):
                raise WorkspaceError('Folders containing linked files cannot be changed.')
            if name == 'delete_file':
                trash_id = uuid4().hex
                base = self.directory(pid) / 'trash' / trash_id
                base.mkdir(parents=True)
                atomic_json(base / 'entry.json', {'id': trash_id, 'path': a['path'], 'created_at': now()})
                source.rename(base / 'content')
                self.save(p)
                return {'deleted': a['path'], 'trash_id': trash_id, 'recoverable': True}
            destination = self.path(pid, a['destination'])
            if destination.exists() or destination.is_relative_to(source):
                raise WorkspaceError('Choose a new destination outside the source folder.')
            destination.parent.mkdir(parents=True, exist_ok=True)
            if name == 'copy_file':
                if source.is_dir():
                    shutil.copytree(source, destination)
                else:
                    shutil.copyfile(source, destination)
            else:
                source.rename(destination)
                for card in p['cards']:
                    path = card.get('path', '')
                    if path == a['path'] or path.startswith(a['path'] + '/'):
                        card['path'] = a['destination'] + path[len(a['path']):]
            self.save(p)
            return {'path': a['destination'], 'saved': True}
        if name in {'list_trash', 'list_versions'}:
            folder = 'trash' if name == 'list_trash' else 'versions'
            entries = [json.loads(path.read_text()) for path in (self.directory(pid) / folder).glob('*/entry.json')]
            if name == 'list_versions':
                entries = [e for e in entries if e['path'] == a['path']]
            return {'entries': sorted(entries, key=lambda e: e['created_at'], reverse=True)}
        if name in {'restore_file', 'restore_version'}:
            folder = 'trash' if name == 'restore_file' else 'versions'
            base = self.directory(pid) / folder / identifier(a['item_id'])
            if not (base / 'entry.json').is_file():
                raise WorkspaceError('Saved item not found.')
            entry = json.loads((base / 'entry.json').read_text())
            target = self.path(pid, entry['path'])
            if name == 'restore_version':
                return self.put(pid, entry['path'], (base / 'content').read_bytes(), a.get('expected_revision'))
            if target.exists():
                raise WorkspaceError('That path is occupied. Rename it before restoring.')
            target.parent.mkdir(parents=True, exist_ok=True)
            (base / 'content').rename(target)
            shutil.rmtree(base)
            self.save(p)
            return {'restored': entry['path']}
        if name == 'save_card':
            kind = a['kind']
            if kind not in KINDS:
                raise WorkspaceError('Choose a supported card type.')
            cid = identifier(a['card_id']) if a.get('card_id') else uuid4().hex
            existing = next((c for c in p['cards'] if c['id'] == cid), None)
            if a.get('card_id') and not existing:
                raise WorkspaceError('Card no longer exists.')
            if not existing and len(p['cards']) >= 200:
                raise WorkspaceError('This project has reached its 200-card limit.')
            card = {**(existing or {}), 'id': cid, 'kind': kind, 'title': text(a['title'], 160, False),
                    'body': text(a.get('body', ''), 12000), 'updated_at': now()}
            for key in ('pinned', 'selected', 'done'):
                if key in a:
                    if not isinstance(a[key], bool):
                        raise WorkspaceError('Card flags must be true or false.')
                    card[key] = a[key]
            if 'path' in a:
                self.path(pid, a['path'])
                card['path'] = a['path']
            if existing:
                p['cards'][p['cards'].index(existing)] = card
            else:
                p['cards'].append(card)
            if card.get('selected'):
                for other in p['cards']:
                    if other['id'] != cid and other['kind'] == kind:
                        other['selected'] = False
            self.save(p)
            return card
        if name == 'delete_card':
            card = next((c for c in p['cards'] if c['id'] == a['card_id']), None)
            if not card:
                raise WorkspaceError('Card not found.')
            p['cards'].remove(card)
            self.save(p)
            return {'deleted': card['id'], 'card': card}
        if name == 'show_board':
            if a['view'] not in {'overview', 'plan', 'parts', 'cad', 'brief', 'files', 'inspiration', 'ideas', 'notes', 'decisions', 'tasks', 'compare', 'file', 'file_editor', 'card', 'trash', 'versions'}:
                raise WorkspaceError('Unknown board view.')
            if a.get('path'):
                self.path(pid, a['path'])
            if a['view'] in {'file', 'file_editor', 'versions'} and not a.get('path'):
                raise WorkspaceError('Choose a file path.')
            if a['view'] == 'file_editor' and not self.read_file(pid, a['path'])['editable']:
                raise WorkspaceError('This file supports reading only.')
            ids = a.get('card_ids', [])
            if any(cid not in {c['id'] for c in p['cards']} for cid in ids) or (a['view'] == 'card' and len(ids) != 1):
                raise WorkspaceError('Choose a saved card to show.')
            self.view = {'id': uuid4().hex, 'project_id': pid, 'view': a['view'], 'path': a.get('path'), 'card_ids': ids, 'query': a.get('query', '')}
            return self.view
        if name == 'set_panel_layout':
            panel = a.get('panel')
            layout = dict(p['layout'])
            if a.get('reset'):
                if panel: layout.pop(panel, None)
                else: layout = {}
            else:
                if panel not in PANEL_DEFAULTS or not any(key in a for key in ('x', 'y', 'width', 'height')):
                    raise WorkspaceError('Choose a panel and at least one position or size.')
                rect = dict(layout.get(panel, PANEL_DEFAULTS[panel]))
                for arg, key in [('x','x'), ('y','y'), ('width','w'), ('height','h')]:
                    if arg in a: rect[key] = a[arg]
                layout[panel] = rect
            self._execute('save_layout', {'project_id': pid, 'layout': layout})
            return {'layout': {**PANEL_DEFAULTS, **layout}}
        if name == 'save_layout':
            layout = a['layout']
            if not isinstance(layout, dict) or len(layout) > 6:
                raise WorkspaceError('Invalid layout.')
            for key, rect in layout.items():
                if key not in {*PANEL_DEFAULTS, 'inspiration'} or not isinstance(rect, dict) or set(rect) != {'x', 'y', 'w', 'h'}:
                    raise WorkspaceError('Invalid panel position.')
                if any(not isinstance(v, (int, float)) or not 0 <= v <= 100 for v in rect.values()):
                    raise WorkspaceError('Invalid panel bounds.')
                if rect['w'] < 10 or rect['h'] < 10 or rect['x'] + rect['w'] > 100.1 or rect['y'] + rect['h'] > 100.1:
                    raise WorkspaceError('Keep panels inside the workspace.')
            p['layout'] = layout
            self.save(p)
            return {'saved': True}
        raise WorkspaceError('Unknown workspace action.')


store = ProjectStore(os.getenv('JARVIS_PROJECTS_DIR', str(ROOT / 'data' / 'projects')))
