"""Compile an atomic workspace snapshot into bounded native panels."""
import hashlib
try:
    from .native_cards import view
    from .view_schema import validate_view, string
except ImportError:
    from native_cards import view
    from view_schema import validate_view, string

SECTIONS = ('brief', 'files', 'ideas', 'plan', 'tasks')


def compile_workspace(data):
    revision = data.get('revision', 0)
    if type(revision) is not int or not 0 <= revision <= 2**53 - 1:
        raise ValueError('Workspace revision must be a nonnegative safe integer')
    if type(data.get('reopen', False)) is not bool:
        raise ValueError('reopen must be boolean')
    panels = []
    for section in SECTIONS:
        if section not in data:
            continue
        values = data[section] if isinstance(data[section], list) else [data[section]]
        if not values:
            continue
        if len(values) > (30 if section == 'tasks' else 64):
            raise ValueError('Too many workspace entries (30 tasks or 64 other entries)')
        spec = view('workspace', {section: values})
        if section in ('files', 'ideas', 'plan'):
            rows = []
            seen = set()
            for i, value in enumerate(values):
                item = value if isinstance(value, dict) else {'label': value}
                label = next((item[k] for k in ('label', 'text', 'title', 'name', 'path', 'description')
                              if isinstance(item.get(k), str) and item[k].strip()), '')
                string(label, 2000)
                identity = str(item.get('id', item.get('path', label)))
                key = 'entry_' + hashlib.sha256(identity.encode()).hexdigest()[:20]
                if key in seen:
                    raise ValueError('Workspace entries need unique IDs or distinct labels')
                seen.add(key)
                row = {'type': 'entry', 'id': key, 'label': label,
                       'detail': string(item.get('detail', ''), 2000),
                       'style': section, 'number': i + 1}
                # File opening stays with the existing agent tools and their authorization.
                if 'prompt' in item:
                    row['prompt'] = string(item['prompt'], 2000)
                elif section == 'files':
                    row['prompt'] = 'Open the workspace file: ' + string(item.get('path', label), 1800)
                rows.append(row)
            spec['layout']['children'] = [spec['layout']['children'][0]] + [
                {'type': 'column', 'children': rows[i:i + 12]} for i in range(0, len(rows), 12)]
            spec = validate_view(spec)
        panels.append({'section': section, 'view': spec})
    if not panels:
        raise ValueError('Workspace requires at least one nonempty section')
    return {'revision': revision, 'reopen': data.get('reopen', False), 'panels': panels}


def legacy_view(workspace):
    state = {}
    sections = []
    for panel in workspace['panels']:
        spec = panel['view']
        state.update(spec['state'])
        children = []
        for node in spec['layout']['children']:
            if panel['section'] not in ('files', 'ideas', 'plan') or node['type'] != 'column':
                children.append(node)
                continue
            rows = []
            for entry in node['children']:
                label = entry['label']
                prompt = entry.get('prompt')
                if prompt and len(label) <= 160:
                    rows.append({'type': 'button', 'label': label, 'prompt': prompt})
                else:
                    rows.append({'type': 'text', 'text': label})
                    if prompt:
                        rows.append({'type': 'button', 'label': 'Use entry', 'prompt': prompt})
                if entry['detail']:
                    rows.append({'type': 'text', 'text': entry['detail'], 'tone': 'muted'})
            children.append({'type': 'column', 'children': rows[:32]})
            if len(rows) > 32:
                children.append({'type': 'column', 'children': rows[32:]})
        sections.append({'type': 'column', 'children': children})

    # shortcut: a legacy workspace fits one view's limits, use the native HUD for larger workspaces.
    return validate_view({'state': state, 'layout': {'type': 'column', 'children': sections}})
