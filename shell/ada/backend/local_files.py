"""Read-only local import sources for hands-free project uploads."""
import json
import os
import stat
from pathlib import Path, PurePosixPath

from .config import ROOT
from .projects import MAX_FILE, WorkspaceError, store


def sources():
    configured = os.getenv('JARVIS_IMPORT_DIRS')
    if configured:
        values = json.loads(configured)
        if not isinstance(values, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in values.items()):
            raise WorkspaceError('Import folders are not configured correctly.')
        return {name: Path(path).expanduser() for name, path in values.items()}
    return {**{name: Path.home() / name for name in ('Documents', 'Downloads', 'Pictures', 'Desktop')},
            'Inbox': ROOT / 'data' / 'inbox'}


def source_path(source, path=''):
    roots = sources()
    if source not in roots:
        raise WorkspaceError('Choose a source returned by list_local_files.')
    root = roots[source]
    if root.is_symlink() or not root.is_dir():
        raise WorkspaceError('That import folder is not available.')
    relative = PurePosixPath(path)
    if '\\' in path or relative.is_absolute() or any(part.startswith('.') for part in relative.parts):
        raise WorkspaceError('Use a relative path inside the chosen import folder.')
    target = root
    for part in relative.parts:
        target = target / part
        if target.is_symlink():
            raise WorkspaceError('Linked files and folders cannot be imported.')
    if not target.resolve().is_relative_to(root.resolve()):
        raise WorkspaceError('Keep imports inside the chosen folder.')
    return target


def list_local_files(source=None, path='', query=''):
    if not source:
        return {'sources': [{'name': name, 'available': root.is_dir() and not root.is_symlink()}
                            for name, root in sources().items()]}
    folder = source_path(source, path)
    if not folder.is_dir():
        raise WorkspaceError('Choose a folder to list.')
    entries = []
    truncated = False
    with os.scandir(folder) as items:
        for i, entry in enumerate(items):
            if i >= 2000:
                truncated = True
                break
            if entry.name.startswith('.') or entry.is_symlink() or query.casefold() not in entry.name.casefold():
                continue
            if not (entry.is_file(follow_symlinks=False) or entry.is_dir(follow_symlinks=False)):
                continue
            entries.append({'path': str(PurePosixPath(path) / entry.name), 'name': entry.name,
                            'folder': entry.is_dir(follow_symlinks=False), 'size': entry.stat(follow_symlinks=False).st_size})
    entries.sort(key=lambda item: (not item['folder'], item['name'].casefold()))
    return {'source': source, 'path': path, 'entries': entries[:100], 'truncated': truncated or len(entries) > 100}


def import_local_file(project_id, source, path, destination=None):
    target = source_path(source, path)
    if not target.is_file():
        raise WorkspaceError('Choose a regular file to import.')
    # Bounded reads, with a final no-follow check; never move or edit the source.
    fd = os.open(target, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise WorkspaceError('Choose a regular file to import.')
        data = stream.read(MAX_FILE + 1)
    if len(data) > MAX_FILE:
        raise WorkspaceError('Files must be no larger than 20 MB.')
    return store.upload(project_id, destination or target.name, data)


def export_local_file(project_id, path, filename=None):
    target = store.path(project_id, path)
    if not target.is_file():
        raise WorkspaceError('Choose a project file to export.')
    name = filename or target.name
    if not name or name.startswith('.') or '/' in name or '\\' in name:
        raise WorkspaceError('Choose a filename without folders.')
    root = sources().get('Downloads')
    if root is None:
        raise WorkspaceError('A Downloads folder must be configured for exports.')
    root.mkdir(parents=True, exist_ok=True)
    destination = source_path('Downloads', name)
    try:
        with target.open('rb') as original, destination.open('xb') as output:
            import shutil
            shutil.copyfileobj(original, output, length=1024 * 1024)
    except FileExistsError:
        raise WorkspaceError('That download already exists. Choose another filename.') from None
    return {'exported': name, 'source': 'Downloads'}
