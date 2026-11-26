"""Read saved parts tables and join them to live stock without rewriting user notes."""
import hashlib
import re

from .inventory import get_inventory
from .projects import store, WorkspaceError
from .image_generation import find_plan


def cells(line):
    return [p.strip() for p in re.split(r'(?<!\\)\|',line.strip().strip('|'))]


def clean(value):
    return re.sub(r'[*_`]', '',value).strip()


def parse_parts(content):
    lines=content.splitlines();rows=[];headers=None;occurrences={};section=''
    for index,line in enumerate(lines):
        if line.startswith('#'):
            section=line.lstrip('#').strip().lower();headers=None
        if '|' not in line:
            headers=None;continue
        values=cells(line)
        if index+1<len(lines) and re.fullmatch(r'[\s|:\-]+',lines[index+1]) and '-' in lines[index+1]:
            labels=[clean(v).casefold() for v in values]
            name=next((i for i,v in enumerate(labels) if v in {'item','part','component','material','part / material'}),None)
            qty=next((i for i,v in enumerate(labels) if v in {'quantity','qty','required','quantity required','required quantity'}),None)
            if name is None or qty is None or any(s in section for s in ('tool','optional','upgrade')):
                headers=None;continue
            headers={'name':name,'quantity':qty,
                'spec':next((i for i,v in enumerate(labels) if 'spec' in v or 'compatib' in v),None),
                'unit':next((i for i,v in enumerate(labels) if v in {'unit','units'}),None),
                'owned':[i for i,v in enumerate(labels) if v in {'already owned','owned','in stock','confirmed stock','available','quantity already owned'}],
                'needed':[i for i,v in enumerate(labels) if v in {'still needed','needed','to buy','quantity still needed'}]}
            continue
        if headers is None or re.fullmatch(r'[\s|:\-]+',line):continue
        if len(values)<=max(v for v in (headers['name'],headers['quantity'],headers['spec'],headers['unit']) if v is not None):
            headers=None;continue
        name=clean(values[headers['name']])
        if not name:continue
        spec=clean(values[headers['spec']]) if headers['spec'] is not None else ''
        raw=clean(values[headers['quantity']]).replace(',','')
        match=re.fullmatch(r'(\d+(?:\.\d+)?)\s*([A-Za-z]*)',raw)
        quantity=float(match[1]) if match else None
        unit=clean(values[headers['unit']]).lower() if headers['unit'] is not None else (match[2].lower() if match else '')
        unit={'':'each','pcs':'each','pc':'each','units':'each','unit':'each','pieces':'each','piece':'each'}.get(unit,unit)
        if quantity is not None and (quantity>1000000 or (unit=='each' and not quantity.is_integer())):quantity=None
        key='|'.join((name.casefold(),spec.casefold(),unit))
        occurrences[key]=occurrences.get(key,0)+1
        key=hashlib.sha256(f'{key}|{occurrences[key]}'.encode()).hexdigest()[:32]
        rows.append({'id':key,'name':name,'specification':spec,'quantity':quantity,'unit':unit,
                     'line_index':index,'columns':headers.copy()})
    return rows


def report(project_id):
    inventory=get_inventory()
    with store.lock:
        project=store.project(project_id)
        paths=[f['path'] for f in store.files(project_id) if not f['folder']]
        path=next((p for p in paths if re.search(r'(?:^|/)parts[ _-]+list\.md$',p,re.I)), '')
        document=store.read_file(project_id,path,limit=262144) if path else {'content':'','revision':''}
        plan=find_plan(store,project_id)
        plan_revision=store.file_revision(store.path(project_id,plan)) if plan else ''
    parsed=parse_parts(document['content'])
    inventory.sync_requirements(project_id,parsed,path,document['revision'])
    with inventory.transaction() as db:
        source=db.execute('SELECT * FROM project_sources WHERE project_id=?',(project_id,)).fetchone()
        if not source or source['parts_revision']!=document['revision']:
            db.execute('INSERT OR REPLACE INTO project_sources VALUES(?,?,?)',(project_id,document['revision'],plan_revision))
            plan_changed=False
        else:plan_changed=source['plan_revision']!=plan_revision
        if project['archived']:
            changed=db.execute('UPDATE requirements SET reserved=0 WHERE project_id=? AND reserved>0',(project_id,))
            if changed.rowcount:inventory.changed(db)
    indexed={r['id']:r for r in inventory.requirements(project_id,[r['id'] for r in parsed])}
    rows=[indexed[r['id']] for r in parsed]
    lines=document['content'].splitlines()
    for original,row in zip(parsed,rows):
        values=cells(lines[original['line_index']])
        for col in original['columns']['owned']:
            if col<len(values):values[col]=f"{row['available']:g} each available" if row['available'] is not None else 'Unknown — match inventory'
        for col in original['columns']['needed']:
            if col<len(values):values[col]=f"{row['needed']:g} {row['unit']}" if row['needed'] is not None else 'Unknown — confirm stock / quantity'
        lines[original['line_index']]='| '+' | '.join(values)+' |'
    return {'project_id':project_id,'source_path':path,'source_revision':document['revision'],
            'plan_changed':plan_changed,'archived':project['archived'],'rows':rows,
            'display_content':'\n'.join(lines),
            'message':('The plan changed after this parts list. Ask Ada to update the parts list before reserving stock.' if plan_changed else
                'Stock is live. Match compatible catalogue parts to calculate shortages; unrecorded stock remains unknown.')}


def project_change(operation, data, request_id):
    current=report(data.get('project_id',''))
    if current['archived']:
        raise WorkspaceError('Open an unarchived project before matching or reserving parts.')
    if current['plan_changed']:
        raise WorkspaceError(current['message'])
    return get_inventory().mutate(operation,data,request_id)
