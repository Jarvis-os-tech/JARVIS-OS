"""Persistent model-request and local CAD-tool records, scoped to one job."""
from datetime import datetime
from uuid import uuid4

from .projects import WorkspaceError, now, store


def duration(started, ended):
    return max(0, round((datetime.fromisoformat(ended) - datetime.fromisoformat(started)).total_seconds(), 1))


class Trace:
    def __init__(self, project_id, job_id, kind, name, **fields):
        self.project_id, self.job_id, self.id = project_id, job_id, uuid4().hex
        with store.lock:
            project = store.project(project_id)
            cad = project.get('cad', {})
            if cad.get('job_id') != job_id or cad.get('status') in {'cancelled', 'interrupted'}:
                raise WorkspaceError('CAD generation was cancelled.')
            entry = {'id': self.id, 'kind': kind, 'name': name, 'status': 'running',
                     'started_at': now(), 'usage': {}, 'summary': '', **fields}
            cad['calls'] = [*cad.get('calls', []), entry][-256:]
            store.save(project)

    def update(self, **fields):
        with store.lock:
            try:
                project = store.project(self.project_id)
            except WorkspaceError:
                return
            cad = project.get('cad', {})
            if cad.get('job_id') != self.job_id or cad.get('status') in {'cancelled', 'interrupted'}:
                return
            entry = next((c for c in cad.get('calls', []) if c['id'] == self.id), None)
            if not entry or entry['status'] != 'running':
                return
            entry.update(fields, last_event_at=now())
            store.save(project)

    def observe(self, event):
        allowed = {'phase', 'summary', 'usage', 'output_characters', 'events', 'model_tool'}
        self.update(**{k: v for k, v in event.items() if k in allowed})

    def finish(self, status='completed', error=''):
        with store.lock:
            try:
                cad = store.project(self.project_id).get('cad', {})
            except WorkspaceError:
                return
            entry = next((c for c in cad.get('calls', []) if c['id'] == self.id), None)
            if entry:
                ended = now()
                self.update(status=status, ended_at=ended, duration_seconds=duration(entry['started_at'], ended), error=error[:4000])


def stop_calls(project_id, job_id, status):
    with store.lock:
        project = store.project(project_id)
        cad = project.get('cad', {})
        if cad.get('job_id') != job_id:
            return
        ended = now()
        for entry in cad.get('calls', []):
            if entry['status'] == 'running':
                entry.update(status=status, ended_at=ended, duration_seconds=duration(entry['started_at'], ended))
        store.save(project)
