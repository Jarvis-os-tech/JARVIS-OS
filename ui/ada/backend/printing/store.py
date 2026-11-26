import json
import sqlite3
import time
import uuid
from contextlib import contextmanager


class Store:
    def __init__(self, root):
        self.root = root; root.mkdir(parents=True, exist_ok=True)
        self.path = root / 'prints.sqlite3'
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS prints (id TEXT PRIMARY KEY, dedupe TEXT UNIQUE, created REAL, payload TEXT)')

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=5)
        try:
            with db: yield db
        finally: db.close()

    def list(self):
        with self.db() as db:
            return [json.loads(row[0]) for row in db.execute('SELECT payload FROM prints ORDER BY created DESC LIMIT 100')]

    def get(self, job_id):
        with self.db() as db:
            row = db.execute('SELECT payload FROM prints WHERE id=?', (job_id,)).fetchone()
        if not row: raise KeyError('Print job not found.')
        return json.loads(row[0])

    def create(self, request, dedupe, title, settings):
        with self.db() as db:
            row = db.execute('SELECT payload FROM prints WHERE dedupe=?', (dedupe,)).fetchone()
            if row: return json.loads(row[0]), False
            job = {'id': uuid.uuid4().hex, 'created': time.time(), 'updated': time.time(),
                   'status': 'queued', 'request': request, 'title': title, 'printer': settings,
                   'error': None, 'filename': None}
            db.execute('INSERT INTO prints VALUES (?,?,?,?)', (job['id'], dedupe, job['created'], json.dumps(job)))
        return job, True

    def update(self, job_id, **fields):
        with self.db() as db:
            row = db.execute('SELECT payload FROM prints WHERE id=?', (job_id,)).fetchone()
            if not row: raise KeyError('Print job not found.')
            job = json.loads(row[0]); job.update(fields, updated=time.time())
            db.execute('UPDATE prints SET payload=? WHERE id=?', (json.dumps(job), job_id))
        return job
