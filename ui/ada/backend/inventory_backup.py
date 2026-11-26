"""Validate a backup and restore into a new directory, preserving existing stock."""
from contextlib import closing
import io
import json
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile
import zipfile

from .inventory import Inventory
from .inventory_camera import CameraSettings
from .projects import WorkspaceError


def restore_archive(data,destination):
    destination=Path(destination)
    if destination.exists():
        raise WorkspaceError('Restore into a new directory so existing inventory remains recoverable.')
    if len(data)>512*1024*1024:
        raise WorkspaceError('This backup exceeds the 512 MB restore limit.')
    destination.parent.mkdir(parents=True,exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix='.ada-restore-',dir=destination.parent) as folder:
            folder=Path(folder)
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                entries=archive.infolist()
                names=[entry.filename for entry in entries]
                if (len(entries)>10000 or len(names)!=len(set(names)) or 'inventory.sqlite3' not in names
                        or sum(e.file_size for e in entries)>1024*1024*1024):
                    raise WorkspaceError('This inventory backup is incomplete or too large.')
                for entry in entries:
                    if entry.filename not in {'inventory.sqlite3','camera.json'} and not re.fullmatch(r'photos/[a-f0-9]{32}\.jpg',entry.filename):
                        raise WorkspaceError('The backup contains an unexpected file.')
                    path=folder/entry.filename;path.parent.mkdir(parents=True,exist_ok=True)
                    path.write_bytes(archive.read(entry))
            dbpath=folder/'inventory.sqlite3'
            with closing(sqlite3.connect(f'{dbpath.as_uri()}?mode=ro',uri=True)) as db:
                db.execute('PRAGMA trusted_schema=OFF')
                if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or db.execute('PRAGMA foreign_key_check').fetchall():
                    raise WorkspaceError('The backup database is damaged.')
                if db.execute("SELECT value FROM metadata WHERE key='schema'").fetchone()[0]!=1:
                    raise WorkspaceError('This backup needs a different version of Ada.')
                for row in db.execute('SELECT data FROM scans'):
                    scan=json.loads(row[0])
                    for photo in scan.get('photos',[]):
                        if not re.fullmatch(r'[a-f0-9]{32}\.jpg',photo) or not (folder/'photos'/photo).is_file():
                            raise WorkspaceError('A saved scan photograph is missing from the backup.')
            if (folder/'camera.json').exists():CameraSettings.model_validate_json((folder/'camera.json').read_text())
            inventory=Inventory(folder);inventory.recover_scans()
            # Checkpoint so the database is self-contained before moving the directory.
            with closing(inventory.connect()) as db:db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
            folder.rename(destination)
    except (zipfile.BadZipFile,sqlite3.Error,ValueError,KeyError,TypeError) as error:
        raise WorkspaceError('The backup could not be validated. Existing stock was not changed.') from None
    return {'directory':str(destination),'restored':True}
