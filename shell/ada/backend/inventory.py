"""Shared local stock, durable scan drafts and an append-only quantity ledger.

Every mutation runs in one SQLite transaction. Request IDs survive reconnects and
process restarts; optimistic revisions protect reviewed quantities from stale UIs.
"""
from __future__ import annotations

from contextlib import contextmanager, closing
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import threading
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .config import ROOT
from .projects import WorkspaceError, now


def uid():
    return uuid4().hex


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Part(Input):
    name: str = Field(min_length=1, max_length=160)
    category: str = Field(default='Other', max_length=80)
    manufacturer: str = Field(default='', max_length=120)
    model: str = Field(default='', max_length=160)
    specifications: dict[str, str] = Field(default_factory=dict, max_length=30)
    aliases: str = Field(default='', max_length=500)
    notes: str = Field(default='', max_length=2000)

    @field_validator('name')
    @classmethod
    def named(cls, value):
        if not value.strip():
            raise ValueError('A part needs a name.')
        return value.strip()

    @field_validator('specifications')
    @classmethod
    def bounded_specs(cls, value):
        if any(not k.strip() or len(k) > 80 or len(v) > 300 for k, v in value.items()):
            raise ValueError('Use short specification names and values.')
        return value


class AddStock(Input):
    part: Part | None = None
    part_id: str = ''
    quantity: int = Field(ge=0, le=1000000)
    location: str = Field(default='', max_length=160)
    condition: str = Field(default='available', pattern='^(available|untested|faulty)$')
    serial: str = Field(default='', max_length=160)


class AdjustStock(Input):
    lot_id: str
    expected_revision: int
    quantity: int = Field(ge=0, le=1000000)
    reason: str = Field(min_length=1, max_length=500)
    project_id: str = ''


class EditPart(Input):
    part_id: str
    expected_revision: int
    part: Part


class EditLot(Input):
    lot_id: str
    expected_revision: int
    location: str = Field(max_length=160)
    condition: str = Field(pattern='^(available|untested|faulty)$')
    serial: str = Field(default='', max_length=160)


class ScanRow(Input):
    id: str = Field(default_factory=uid)
    part: Part
    quantity: int = Field(ge=1, le=1000000)
    part_id: str = ''
    lot_id: str = ''
    location: str = Field(default='', max_length=160)
    condition: str = Field(default='available', pattern='^(available|untested|faulty)$')
    serial: str = Field(default='', max_length=160)
    label_text: str = Field(default='', max_length=2000)
    uncertainties: str = Field(default='', max_length=2000)
    boxes: list[list[int]] = Field(default_factory=list, max_length=100)
    confirmed: bool = False
    saved: bool = False
    lot_revision: int | None = None
    part_revision: int | None = None
    suggested_part_ids: list[str] = Field(default_factory=list,max_length=100)
    detail_photo: str = ''

    @field_validator('boxes')
    @classmethod
    def valid_boxes(cls, value):
        for box in value:
            if (len(box) != 4 or any(type(n) is not int or n < 0 or n > 1000 for n in box)
                    or box[0] >= box[2] or box[1] >= box[3]):
                raise ValueError('Invalid object outline.')
        return value


class ScanEdit(Input):
    scan_id: str
    expected_revision: int
    row: ScanRow


class ScanConfirm(Input):
    scan_id: str
    expected_revision: int
    row_ids: list[str] = Field(min_length=1,max_length=100)
    confirmed: bool


class ScanDiscard(Input):
    scan_id: str
    expected_revision: int


class MatchRequirement(Input):
    project_id: str
    requirement_id: str
    source_revision: str
    part_id: str = ''
    confirmed: bool = False


class Reservation(Input):
    project_id: str
    requirement_id: str
    source_revision: str
    quantity: int = Field(ge=0,le=1000000)


class Undo(Input):
    operation_id: str


INPUTS={'add_stock':AddStock,'adjust_stock':AdjustStock,'edit_part':EditPart,'edit_lot':EditLot,
        'edit_scan':ScanEdit,'confirm_scan':ScanConfirm,'discard_scan':ScanDiscard,
        'match_requirement':MatchRequirement,'reserve':Reservation,'undo':Undo}


SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value INTEGER NOT NULL);
INSERT OR IGNORE INTO metadata VALUES ('schema',1),('revision',0);
CREATE TABLE IF NOT EXISTS parts (
 id TEXT PRIMARY KEY, data TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS lots (
 id TEXT PRIMARY KEY, part_id TEXT NOT NULL REFERENCES parts(id),
 quantity INTEGER NOT NULL CHECK(quantity>=0), location TEXT NOT NULL,
 condition TEXT NOT NULL, serial TEXT NOT NULL DEFAULT '', revision INTEGER NOT NULL DEFAULT 1);
CREATE INDEX IF NOT EXISTS lots_part ON lots(part_id);
CREATE TABLE IF NOT EXISTS operations (
 id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, result TEXT NOT NULL,
 kind TEXT NOT NULL, created_at TEXT NOT NULL, undone INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS movements (
 id INTEGER PRIMARY KEY, operation_id TEXT NOT NULL REFERENCES operations(id),
 lot_id TEXT NOT NULL REFERENCES lots(id), before_quantity INTEGER NOT NULL,
 after_quantity INTEGER NOT NULL, after_revision INTEGER NOT NULL, reason TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS scans (
 id TEXT PRIMARY KEY, request_id TEXT UNIQUE NOT NULL, data TEXT NOT NULL,
 revision INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS requirements (
 project_id TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL,
 specification TEXT NOT NULL, quantity REAL, unit TEXT NOT NULL, part_id TEXT REFERENCES parts(id),
 reserved INTEGER NOT NULL DEFAULT 0 CHECK(reserved>=0), source_path TEXT NOT NULL,
 source_revision TEXT NOT NULL, PRIMARY KEY(project_id,id));
CREATE TABLE IF NOT EXISTS project_sources (
 project_id TEXT PRIMARY KEY, parts_revision TEXT NOT NULL, plan_revision TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS evidence (
 part_id TEXT NOT NULL REFERENCES parts(id), scan_id TEXT NOT NULL REFERENCES scans(id),
 row_id TEXT NOT NULL, data TEXT NOT NULL, PRIMARY KEY(part_id,scan_id,row_id));
"""


class Inventory:
    def __init__(self, root):
        self.root = Path(root)
        self.lock = threading.RLock()
        self.root.mkdir(parents=True, exist_ok=True)
        self.photos = self.root / 'photos'
        self.photos.mkdir(exist_ok=True)
        self.db = self.root / 'inventory.sqlite3'
        with closing(self.connect()) as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript(SCHEMA)
            db.commit()
            if db.execute("SELECT value FROM metadata WHERE key='schema'").fetchone()[0] != 1:
                raise WorkspaceError('This inventory needs a newer version of Ada.')

    def connect(self):
        db = sqlite3.connect(self.db, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        return db

    @contextmanager
    def transaction(self):
        with self.lock:
            db = self.connect()
            try:
                db.execute('BEGIN IMMEDIATE')
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise
            finally:
                db.close()

    @staticmethod
    def changed(db):
        db.execute("UPDATE metadata SET value=value+1 WHERE key='revision'")

    @staticmethod
    def require(db, table, key):
        # Table is an internal constant, never a request parameter.
        row = db.execute(f'SELECT * FROM {table} WHERE id=?', (key,)).fetchone()
        if row is None:
            raise WorkspaceError('The inventory item no longer exists. Refresh and try again.')
        return row

    @staticmethod
    def revision(row, expected):
        if row['revision'] != expected:
            raise WorkspaceError('This item changed since it was reviewed. Refresh before saving.')

    def _part(self, db, part_id):
        row = self.require(db, 'parts', part_id)
        evidence=[json.loads(r['data']) for r in db.execute('SELECT data FROM evidence WHERE part_id=? ORDER BY rowid DESC LIMIT 10',(part_id,))]
        return {'id': row['id'], 'revision': row['revision'], **json.loads(row['data']), 'evidence':evidence}

    def _stock(self, db, part_id):
        total = db.execute('SELECT coalesce(sum(quantity),0) FROM lots WHERE part_id=?', (part_id,)).fetchone()[0]
        usable = db.execute("SELECT coalesce(sum(quantity),0) FROM lots WHERE part_id=? AND condition='available'", (part_id,)).fetchone()[0]
        reserved = db.execute('SELECT coalesce(sum(reserved),0) FROM requirements WHERE part_id=?', (part_id,)).fetchone()[0]
        return {'quantity': total, 'usable': usable, 'reserved': reserved, 'available': max(0, usable-reserved)}

    def snapshot(self, query=''):
        with self.transaction() as db:
            items = []
            for row in db.execute('SELECT id FROM parts ORDER BY created_at DESC'):
                part = self._part(db, row['id'])
                if query.casefold() not in encoded(part).casefold():
                    continue
                lots = [dict(r) for r in db.execute('SELECT * FROM lots WHERE part_id=?', (part['id'],))]
                part.update(self._stock(db, part['id']))
                part['lots'] = lots
                items.append(part)
            scans = [self._scan(r) for r in db.execute('SELECT * FROM scans ORDER BY created_at DESC LIMIT 30')]
            history = []
            for row in db.execute('SELECT * FROM operations ORDER BY created_at DESC LIMIT 50'):
                history.append({'id': row['id'], 'kind': row['kind'], 'created_at': row['created_at'],
                                'undone': bool(row['undone']), 'result': json.loads(row['result'])})
            return {'revision': db.execute("SELECT value FROM metadata WHERE key='revision'").fetchone()[0],
                    'items': items, 'scans': scans, 'history': history}

    def mutate(self, kind, payload, request_id):
        if not isinstance(request_id, str) or not 1 <= len(request_id) <= 200:
            raise WorkspaceError('A unique request ID is required.')
        fingerprint = hashlib.sha256(encoded([kind, payload]).encode()).hexdigest()
        with self.transaction() as db:
            previous = db.execute('SELECT * FROM operations WHERE id=?', (request_id,)).fetchone()
            if previous:
                if previous['fingerprint'] != fingerprint:
                    raise WorkspaceError('This request ID was already used for another change.')
                return json.loads(previous['result'])
            db.execute('INSERT INTO operations(id,fingerprint,result,kind,created_at) VALUES(?,?,?,?,?)',
                       (request_id, fingerprint, '{}', kind, now()))
            handlers = {'add_stock': self._add, 'adjust_stock': self._adjust, 'edit_part': self._edit_part,
                        'edit_lot': self._edit_lot, 'undo': self._undo, 'match_requirement': self._match,
                        'reserve': self._reserve, 'edit_scan': self._edit_scan, 'confirm_scan': self._confirm_scan,
                        'discard_scan': self._discard_scan}
            if kind not in handlers:
                raise WorkspaceError('Unknown inventory change.')
            try:
                checked = INPUTS[kind].model_validate(payload).model_dump()
                result = handlers[kind](db, checked, request_id)
            except ValidationError as error:
                raise WorkspaceError('Check the inventory fields: ' + error.errors()[0]['msg']) from None
            result = {**result, 'operation_id': request_id}
            db.execute('UPDATE operations SET result=? WHERE id=?', (encoded(result), request_id))
            self.changed(db)
            return result

    def _movement(self, db, lot, quantity, request_id, reason):
        if quantity < 0:
            raise WorkspaceError('Stock cannot be negative.')
        revision = lot['revision'] + 1
        db.execute('UPDATE lots SET quantity=?,revision=? WHERE id=?', (quantity, revision, lot['id']))
        db.execute('INSERT INTO movements(operation_id,lot_id,before_quantity,after_quantity,after_revision,reason) VALUES(?,?,?,?,?,?)',
                   (request_id, lot['id'], lot['quantity'], quantity, revision, reason))
        self._check_reservations(db, lot['part_id'])

    def _check_reservations(self, db, part_id):
        stock = self._stock(db, part_id)
        if stock['reserved'] > stock['usable']:
            raise WorkspaceError('Some of this stock is reserved. Release the reservation or record usage for that project first.')

    def _add(self, db, payload, request_id):
        data = AddStock.model_validate(payload)
        if data.serial and data.quantity != 1:
            raise WorkspaceError('A serial-numbered item must have quantity one.')
        part_id = data.part_id
        if part_id:
            self.require(db, 'parts', part_id)
        else:
            if data.part is None:
                raise WorkspaceError('Give the new part a name and its known details.')
            part_id = uid()
            db.execute('INSERT INTO parts(id,data,created_at) VALUES(?,?,?)', (part_id, encoded(data.part.model_dump()), now()))
        if data.serial and db.execute('SELECT 1 FROM lots WHERE part_id=? AND serial=?', (part_id, data.serial)).fetchone():
            raise WorkspaceError('That serial number is already recorded for this part.')
        lot = None if data.serial else db.execute('SELECT * FROM lots WHERE part_id=? AND location=? AND condition=? AND serial=?',
                    (part_id, data.location, data.condition, '')).fetchone()
        if lot is None:
            lot_id = uid()
            db.execute('INSERT INTO lots(id,part_id,quantity,location,condition,serial) VALUES(?,?,0,?,?,?)',
                       (lot_id, part_id, data.location, data.condition, data.serial))
            lot = self.require(db, 'lots', lot_id)
        self._movement(db, lot, lot['quantity'] + data.quantity, request_id, 'Stock added')
        return {'part_id': part_id, 'lot_id': lot['id'], **self._stock(db, part_id)}

    def _adjust(self, db, payload, request_id):
        data = AdjustStock.model_validate(payload)
        lot = self.require(db, 'lots', data.lot_id)
        self.revision(lot, data.expected_revision)
        if lot['serial'] and data.quantity>1:
            raise WorkspaceError('A serial-numbered batch can contain at most one unit.')
        if data.project_id and data.quantity < lot['quantity']:
            remaining = lot['quantity'] - data.quantity
            for row in db.execute('SELECT * FROM requirements WHERE project_id=? AND part_id=? ORDER BY id', (data.project_id, lot['part_id'])).fetchall():
                release = min(row['reserved'], remaining)
                db.execute('UPDATE requirements SET reserved=reserved-? WHERE project_id=? AND id=?', (release, data.project_id, row['id']))
                remaining -= release
        self._movement(db, lot, data.quantity, request_id, data.reason)
        return {'part_id': lot['part_id'], 'lot_id': lot['id'], **self._stock(db, lot['part_id'])}

    def _edit_part(self, db, payload, request_id):
        data = EditPart.model_validate(payload)
        row = self.require(db, 'parts', data.part_id)
        self.revision(row, data.expected_revision)
        old = json.loads(row['data'])
        if any(old[k] != data.part.model_dump()[k] for k in ('model','manufacturer','specifications')):
            db.execute('UPDATE requirements SET part_id=NULL,reserved=0 WHERE part_id=?', (data.part_id,))
        db.execute('UPDATE parts SET data=?,revision=revision+1 WHERE id=?', (encoded(data.part.model_dump()), data.part_id))
        return self._part(db, data.part_id)

    def _edit_lot(self, db, payload, request_id):
        data = EditLot.model_validate(payload)
        lot = self.require(db, 'lots', data.lot_id)
        self.revision(lot, data.expected_revision)
        if data.serial and (lot['quantity'] != 1 or db.execute('SELECT 1 FROM lots WHERE part_id=? AND serial=? AND id!=?',
                (lot['part_id'], data.serial, data.lot_id)).fetchone()):
            raise WorkspaceError('A serial number must identify one distinct item.')
        db.execute('UPDATE lots SET location=?,condition=?,serial=?,revision=revision+1 WHERE id=?',
                   (data.location, data.condition, data.serial, data.lot_id))
        self._check_reservations(db, lot['part_id'])
        return dict(self.require(db, 'lots', data.lot_id))

    def _undo(self, db, payload, request_id):
        original = self.require(db, 'operations', payload.get('operation_id'))
        if original['undone']:
            raise WorkspaceError('That change has already been undone.')
        if original['kind'] not in {'add_stock','adjust_stock','confirm_scan'}:
            raise WorkspaceError('Only stock quantity changes can be undone here.')
        changes = db.execute('SELECT * FROM movements WHERE operation_id=? ORDER BY id DESC', (original['id'],)).fetchall()
        if not changes:
            raise WorkspaceError('That change did not alter any stock.')
        checked = set()
        for change in changes:
            lot = self.require(db, 'lots', change['lot_id'])
            if lot['id'] not in checked:
                self.revision(lot, change['after_revision'])
                checked.add(lot['id'])
            self._movement(db, lot, change['before_quantity'], request_id, 'Undo ' + original['id'])
        db.execute('UPDATE operations SET undone=1 WHERE id=?', (original['id'],))
        return {'undone': original['id'], 'note': 'Project reservations are not recreated by undo.'}

    @staticmethod
    def _scan(row):
        return {'id': row['id'], 'revision': row['revision'], 'created_at': row['created_at'], **json.loads(row['data'])}

    def scan(self, scan_id):
        with self.transaction() as db:
            return self._scan(self.require(db, 'scans', scan_id))

    def create_scan(self, request_id, mode, location):
        if mode not in {'add','recount'} or not isinstance(location,str) or len(location)>160 or not 1<=len(request_id)<=200:
            raise WorkspaceError('Choose Add stock or Recount and a short storage location.')
        with self.transaction() as db:
            existing = db.execute('SELECT * FROM scans WHERE request_id=?', (request_id,)).fetchone()
            if existing:
                data = self._scan(existing)
                if data['mode'] != mode or data['location'] != location:
                    raise WorkspaceError('This scan request was already used.')
                return data, False
            if db.execute("SELECT 1 FROM scans WHERE json_extract(data,'$.status') IN ('capturing','analysing','refining')").fetchone():
                raise WorkspaceError('A scan is already running. Review it before starting another.')
            scan_id = uid()
            data = {'status': 'capturing', 'mode': mode, 'location': location, 'rows': [], 'photos': [], 'message': ''}
            db.execute('INSERT INTO scans(id,request_id,data,created_at) VALUES(?,?,?,?)', (scan_id,request_id,encoded(data),now()))
            self.changed(db)
            return self._scan(self.require(db,'scans',scan_id)), True

    def update_scan_job(self, scan_id, **updates):
        with self.transaction() as db:
            row = self.require(db,'scans',scan_id)
            data = json.loads(row['data'])
            if data['status'] in {'discarded','complete'}:
                return
            data.update(updates)
            self._save_scan(db,scan_id,data)

    def _save_scan(self, db, scan_id, data):
        db.execute('UPDATE scans SET data=?,revision=revision+1 WHERE id=?', (encoded(data),scan_id))
        self.changed(db)

    def recover_scans(self):
        with self.transaction() as db:
            for row in db.execute('SELECT * FROM scans').fetchall():
                data=json.loads(row['data'])
                if data['status'] in {'capturing','analysing','refining'}:
                    data.update(status='review' if data['rows'] else 'error',message='This scan was interrupted. Its photographs and review entries are saved. No additional stock was added.')
                    self._save_scan(db,row['id'],data)

    def _reviewable(self, db, payload):
        row=self.require(db,'scans',payload.get('scan_id'))
        self.revision(row,payload.get('expected_revision'))
        data=json.loads(row['data'])
        if data['status'] != 'review':
            raise WorkspaceError('This scan is not waiting for review.')
        return row,data

    def _edit_scan(self, db, payload, request_id):
        scan,data=self._reviewable(db,payload)
        updated=ScanRow.model_validate(payload.get('row'))
        rows=data['rows']
        index=next((i for i,r in enumerate(rows) if r['id']==updated.id),None)
        if index is None or rows[index].get('saved'):
            raise WorkspaceError('Choose an unsaved item from this scan.')
        updated.saved=False
        if updated.part_id:
            part=self.require(db,'parts',updated.part_id)
            if updated.part_revision is not None:self.revision(part,updated.part_revision)
            elif updated.confirmed:raise WorkspaceError('Read the selected catalogue part and include its revision before confirming.')
            known=json.loads(part['data'])
            normal=lambda value:re.sub(r'\s+','',value).casefold()
            if known['model'] and updated.part.model and normal(known['model'])!=normal(updated.part.model):
                raise WorkspaceError('The selected catalogue model differs from this scan. Correct the identity or choose another part.')
            for key,value in updated.part.specifications.items():
                recorded=next((v for k,v in known['specifications'].items() if normal(k)==normal(key)),None)
                if recorded and value and normal(recorded)!=normal(value):
                    raise WorkspaceError('The selected part has a different '+key+'. Correct the details or choose another part.')
            updated.part_revision=part['revision']
        else:updated.part_revision=None
        if updated.lot_id:
            lot=self.require(db,'lots',updated.lot_id)
            if lot['part_id']!=updated.part_id:
                raise WorkspaceError('The storage batch must belong to the selected part.')
            if updated.lot_revision is not None:self.revision(lot,updated.lot_revision)
            elif updated.confirmed and data['mode']=='recount':raise WorkspaceError('Read the storage batch and include its revision before confirming a recount.')
            updated.lot_revision=lot['revision']
        else:
            updated.lot_revision=None
        rows[index]=updated.model_dump()
        self._save_scan(db,scan['id'],data)
        return self._scan(self.require(db,'scans',scan['id']))

    def _confirm_scan(self, db, payload, request_id):
        scan,data=self._reviewable(db,payload)
        ids=payload.get('row_ids')
        if payload.get('confirmed') is not True or not isinstance(ids,list) or not ids or len(set(ids))!=len(ids):
            raise WorkspaceError('Confirm the exact scan items to save.')
        selected=[r for r in data['rows'] if r['id'] in ids and not r.get('saved')]
        if len(selected)!=len(ids) or any(not r['confirmed'] for r in selected):
            raise WorkspaceError('Review and confirm each selected identity and quantity first.')
        recount_lots=set()
        saved=[]
        for raw in selected:
            row=ScanRow.model_validate(raw)
            if row.part_id:self.revision(self.require(db,'parts',row.part_id),row.part_revision)
            if data['mode']=='recount':
                if not row.lot_id or row.lot_revision is None or row.lot_id in recount_lots:
                    raise WorkspaceError('For a recount, select each existing storage batch once.')
                recount_lots.add(row.lot_id)
                result=self._adjust(db,{'lot_id':row.lot_id,'expected_revision':row.lot_revision,
                    'quantity':row.quantity,'reason':'Camera recount'},request_id)
            else:
                result=self._add(db,{'part_id':row.part_id,'part':row.part.model_dump(),
                    'quantity':row.quantity,'location':row.location,'condition':row.condition,'serial':row.serial},request_id)
            raw.update(saved=True,part_id=result['part_id'],lot_id=result['lot_id'])
            db.execute('INSERT OR REPLACE INTO evidence VALUES(?,?,?,?)',(result['part_id'],scan['id'],row.id,
                encoded({'scan_id':scan['id'],'row_id':row.id,'photos':data['photos'],'boxes':row.boxes,
                         'label_text':row.label_text,'detail_photo':row.detail_photo})))
            saved.append(result)
        data['status']='complete' if all(r['saved'] for r in data['rows']) else 'review'
        self._save_scan(db,scan['id'],data)
        return {'scan_id':scan['id'],'saved':saved,'status':data['status']}

    def _discard_scan(self, db, payload, request_id):
        row=self.require(db,'scans',payload.get('scan_id'))
        self.revision(row,payload.get('expected_revision'))
        data=json.loads(row['data'])
        data['status']='discarded'
        self._save_scan(db,row['id'],data)
        return {'discarded':row['id'],'note':'Previously saved stock is unchanged; use Undo to reverse it.'}

    def sync_requirements(self, project_id, requirements, source_path, source_revision):
        with self.transaction() as db:
            existing={r['id']:dict(r) for r in db.execute('SELECT * FROM requirements WHERE project_id=?',(project_id,))}
            incoming={r['id'] for r in requirements}
            changed=False
            for key in existing.keys()-incoming:
                db.execute('DELETE FROM requirements WHERE project_id=? AND id=?',(project_id,key));changed=True
            for r in requirements:
                old=existing.get(r['id'])
                if old and old['source_revision']==source_revision and old['source_path']==source_path:
                    continue
                reserved=min(old['reserved'],int(r['quantity'] or 0)) if old else 0
                db.execute('INSERT INTO requirements VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(project_id,id) DO UPDATE SET '
                           'quantity=excluded.quantity,reserved=excluded.reserved,source_path=excluded.source_path,source_revision=excluded.source_revision',
                           (project_id,r['id'],r['name'],r['specification'],r['quantity'],r['unit'],old['part_id'] if old else None,
                            reserved,source_path,source_revision));changed=True
            if changed:self.changed(db)

    def requirements(self, project_id, order=None):
        with self.transaction() as db:
            rows=[dict(r) for r in db.execute('SELECT * FROM requirements WHERE project_id=? ORDER BY rowid',(project_id,))]
            if order:
                positions={key:i for i,key in enumerate(order)}
                rows.sort(key=lambda r:positions.get(r['id'],len(positions)))
            # Allocate the shared free pool once across repeated requirements.
            pools={}
            for r in rows:
                r.update(available=None,needed=None,on_hand=None,part=None)
                if r['part_id']:
                    part_id=r['part_id']; stock=self._stock(db,part_id)
                    r['part']=self._part(db,part_id);r['on_hand']=stock['quantity']
                    free=pools.setdefault(part_id,stock['available'])
                    r['available']=free+r['reserved']
                    if r['quantity'] is not None:
                        r['needed']=max(0,r['quantity']-r['available'])
                        pools[part_id]=max(0,free-max(0,r['quantity']-r['reserved']))
            return rows

    def _requirement(self, db, payload):
        row=db.execute('SELECT * FROM requirements WHERE project_id=? AND id=?',
                       (payload.get('project_id'),payload.get('requirement_id'))).fetchone()
        if not row or row['source_revision']!=payload.get('source_revision'):
            raise WorkspaceError('The parts plan changed. Read its current stock report before editing.')
        return row

    def _match(self, db, payload, request_id):
        row=self._requirement(db,payload)
        part_id=payload.get('part_id') or None
        if part_id:
            if payload.get('confirmed') is not True or row['unit']!='each':
                raise WorkspaceError('Confirm a compatible part with matching units before linking stock.')
            self.require(db,'parts',part_id)
        db.execute('UPDATE requirements SET part_id=?,reserved=0 WHERE project_id=? AND id=?',
                   (part_id,row['project_id'],row['id']))
        return {'matched':part_id,'requirement_id':row['id']}

    def _reserve(self, db, payload, request_id):
        row=self._requirement(db,payload)
        quantity=payload.get('quantity')
        if not row['part_id'] or type(quantity) is not int or quantity<0 or row['quantity'] is None or quantity>row['quantity']:
            raise WorkspaceError('Choose a linked part and reserve no more than this project requires.')
        db.execute('UPDATE requirements SET reserved=? WHERE project_id=? AND id=?',(quantity,row['project_id'],row['id']))
        self._check_reservations(db,row['part_id'])
        return {'reserved':quantity,'requirement_id':row['id']}

    def photo_path(self, name):
        if not re.fullmatch(r'[a-f0-9]{32}\.jpg',name):
            raise WorkspaceError('Choose a saved inventory photograph.')
        path=self.photos/name
        if path.is_symlink() or not path.is_file():
            raise WorkspaceError('Inventory photograph not found.')
        return path


@lru_cache(maxsize=8)
def _inventory(root):
    return Inventory(root)


def get_inventory():
    return _inventory(os.getenv('JARVIS_INVENTORY_DIR',str(ROOT/'data'/'inventory')))
