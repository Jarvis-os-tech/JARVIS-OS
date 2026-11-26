"""Session-scoped deletion requests, confirmed by a separate user utterance."""
import re
import time
from uuid import uuid4

from .projects import WorkspaceError, store

DELETION_ACTIONS = {'delete_project', 'confirm_project_deletion', 'cancel_project_deletion'}


class ProjectDeletion:
    def __init__(self):
        self.pending = None

    def run(self, name, arguments, *, sequence, request, context_id):
        with store.lock:
            if store.active() != context_id:
                raise WorkspaceError('The conversation changed projects. Request deletion again.')
            if name == 'cancel_project_deletion':
                self.pending = None
                return {'cancelled': True, 'deleted': False}
            if name == 'delete_project':
                project = store.project(arguments['project_id'])
                self.pending = dict(project_id=project['id'], revision=project['revision'],
                                    confirmation_id=uuid4().hex, sequence=sequence,
                                    expires=time.monotonic() + 120, asked=False)
                return {'confirmation_required': True, 'deleted': False,
                        'project_id': project['id'], 'confirmation_id': self.pending['confirmation_id'],
                        'question': f'Delete "{project["name"]}" and all its files and saved ideas from your library? '
                                    'A recovery copy will remain on disk. Say "yes, delete it" to confirm, or "cancel".'}
            pending = self.pending
            if not pending or pending['confirmation_id'] != arguments['confirmation_id'] or pending['project_id'] != arguments['project_id']:
                raise WorkspaceError('No matching deletion request. Ask for confirmation first.')
            if not pending['asked'] or sequence <= pending['sequence']:
                raise WorkspaceError('Ask the confirmation question and wait for a separate user reply.')
            answer = re.sub(r'[^\w\s]', '', request.casefold()).strip()
            answer = ' '.join(answer.split())
            approved = answer in {'yes', 'yes please', 'yes delete it', 'yes please delete it',
                                  'delete it', 'confirm deletion', 'yes delete the project'}
            self.pending = None
            if sequence != pending['sequence'] + 1 or time.monotonic() > pending['expires'] or not approved:
                raise WorkspaceError('Deletion was not confirmed. Nothing was deleted; ask again if needed.')
            return self.delete(pending)

    @staticmethod
    def delete(pending):
        from .inventory import get_inventory
        pid = pending['project_id']
        project = store.project(pid)
        if project['revision'] != pending['revision']:
            raise WorkspaceError('The project changed after the question. Ask for confirmation again.')
        source = store.directory(pid)
        trash = store.root / '.deleted'
        if trash.is_symlink():
            raise WorkspaceError('Linked recovery folders are not supported.')
        trash.mkdir(exist_ok=True)
        destination = trash / pid
        if destination.exists():
            raise WorkspaceError('A recovery copy already exists; nothing was deleted.')
        active = store.active()
        moved = False
        try:
            inventory = get_inventory()
            with inventory.transaction() as db:
                db.execute('DELETE FROM requirements WHERE project_id=?', (pid,))
                db.execute('DELETE FROM project_sources WHERE project_id=?', (pid,))
                inventory.changed(db)
                if active == pid:
                    store.activate(None)
                source.rename(destination)
                moved = True
        except BaseException:
            if moved:
                destination.rename(source)
            if active == pid:
                store.activate(pid)
            raise
        if store.view and store.view.get('project_id') == pid:
            store.view = None
        return {'deleted': True, 'project_id': pid, 'name': project['name'], 'recoverable': True}
