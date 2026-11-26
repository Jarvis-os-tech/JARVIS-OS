import asyncio
import hashlib
import json
import logging
import os
import shutil
import time
from pathlib import Path
from ..config import ROOT
from .models import PrinterSettings, PrintRequest
from . import plate
from .printer import Printer, PrinterError
from .slicer import Slicer, profile_revision, profile_text
from .store import Store

ACTIVE = {'uploading', 'starting', 'start_unknown', 'printing', 'paused'}
logger = logging.getLogger(__name__)


class PrintService:
    def __init__(self, root=None, slicer=None, printer_factory=Printer, cad=None):
        self.root = Path(root or os.getenv('JARVIS_PRINT_DATA', str(ROOT / 'data/printing')))
        self.store = Store(self.root); self.slicer = slicer or Slicer()
        self.printer_factory = printer_factory; self.cad = cad
        self.lock = asyncio.Lock(); self.slice_lock = asyncio.Lock(); self.tasks = {}; self.operations = set()
        self.monitor = None; self.closed = False
        self.cached = {'connected':False, 'ready':False, 'state':'checking', 'message':'Checking printer…'}

    def settings(self):
        try:
            settings = PrinterSettings.model_validate_json((self.root / 'settings.json').read_text())
            if settings.profile_revision != profile_revision(): settings.profile_verified = False
            return settings
        except FileNotFoundError: return PrinterSettings()

    async def db(self, method, *args, **kwargs):
        return await asyncio.to_thread(getattr(self.store, method), *args, **kwargs)

    async def save_settings(self, settings):
        async with self.lock:
            if any(j['status'] in ACTIVE for j in await self.db('list')):
                raise ValueError('Finish or resolve the current print before changing printer settings.')
            old = self.settings()
            # Verification belongs to a completed calibration, not an editable checkbox.
            values = settings.model_dump(); values['profile_verified'] = old.profile_verified
            values['profile_revision'] = old.profile_revision
            if any(getattr(old,k) != getattr(settings,k) for k in ['host','port','hostname','material','source','cfs_box','cfs_slot']):
                values['profile_verified'] = False
            temp = self.root / 'settings.tmp'; temp.write_text(json.dumps(values, indent=2))
            temp.replace(self.root / 'settings.json')
            return self.settings().model_dump()

    async def status(self):
        settings = self.settings()
        if not settings.host:
            self.cached = {'connected':False, 'ready':False, 'state':'unconfigured', 'message':'Set your printer IP.'}
            return self.cached
        try: self.cached = await self.printer_factory(settings).status()
        except PrinterError as exc:
            if self.cached.get('state') != 'offline' or self.cached.get('message') != str(exc):
                logger.warning('Printer check failed at %s:%s: %s', settings.host, settings.port, exc)
            self.cached = {'connected':False, 'ready':False, 'state':'offline', 'message':str(exc)}
        return self.cached

    async def recover(self):
        self.closed = False
        for job in await self.db('list'):
            if job['status'] in {'queued','slicing','uploading'}:
                await self.db('update', job['id'], status='failed', error='Preparation was interrupted. Prepare a new print; nothing is automatically restarted.')
            elif job['status'] == 'starting':
                await self.db('update', job['id'], status='start_unknown', error='Reconnecting to check whether the print started. Do not start it again.')
        self.monitor = asyncio.create_task(self.watch())

    async def watch(self):
        while True:
            try:
                status = await self.status()
                if status.get('connected'):
                    async with self.lock:
                        for job in await self.db('list'):
                            if job['status'] not in ACTIVE:
                                continue
                            if job.get('filename') != status.get('filename'):
                                if job['status']=='starting' and time.time()-job.get('started_at',time.time())>30:
                                    await self.db('update',job['id'],status='start_unknown',error='The printer has not confirmed this file started. Check its screen before resolving this job.')
                                continue
                            state = status['state']
                            mapping = {'printing':'printing','paused':'paused','complete':'complete','cancelled':'canceled','error':'failed'}
                            if state in mapping:
                                await self.db('update', job['id'], status=mapping[state], error=status.get('message') if state=='error' else None)
            except asyncio.CancelledError: raise
            except Exception:
                logger.exception('Printer monitoring interrupted')
                self.cached = {'connected':False,'ready':False,'state':'offline','message':'Printer monitoring interrupted; reconnecting.'}
            await asyncio.sleep(3)

    async def create(self, request, key):
        task = asyncio.create_task(self._create(request, key)); self.operations.add(task)
        task.add_done_callback(self.operation_done)
        return await asyncio.shield(task)

    def operation_done(self, task):
        self.operations.discard(task)
        if not task.cancelled(): task.exception()

    async def _create(self, request, key):
        request = PrintRequest.model_validate(request).model_dump()
        async with self.lock:
            if self.closed: raise ValueError('Printing service is shutting down.')
            if len(self.tasks) >= 3: raise ValueError('Slicing queue is full.')
            settings = self.settings()
            if settings.source == 'unknown' or settings.material == 'unknown':
                raise ValueError('Set the loaded filament and feed source in Printing settings first.')
            if request['material'] != settings.material:
                raise ValueError('Selected material does not match the configured loaded filament.')
            report = await asyncio.to_thread(plate.inspect, request)
            if not report['valid']:
                raise ValueError(' '.join(report['errors']))
            job, created = await self.db('create', request, key, report['title'], settings.model_dump())
            if not created and job['request'] != request:
                raise ValueError('This request ID belongs to a different plate. Prepare again.')
            if created:
                folder = self.root / job['id']; folder.mkdir()
                report = await asyncio.to_thread(plate.inspect, request, output=folder / 'model.stl')
                if not report['valid']:
                    await self.db('update', job['id'], status='failed', error='CAD changed during preparation.')
                    raise ValueError('CAD changed during preparation. Review again.')
                size = [max(p['bounds'][1][k] for p in report['parts']) - min(p['bounds'][0][k] for p in report['parts']) for k in range(3)]
                await self.db('update', job['id'], size_mm=size, plate=report)
                self.tasks[job['id']] = asyncio.create_task(self.prepare(job))
                self.tasks[job['id']].add_done_callback(lambda _: self.tasks.pop(job['id'],None))
            return job

    async def prepare(self, job):
        try:
            async with self.slice_lock:
                await self.db('update', job['id'], status='slicing')
                request = {**job['request'], 'source':job['printer']['source']}
                summary = await self.slicer.slice(self.root / job['id'], request)
                fingerprint = hashlib.sha256(json.dumps({'summary':summary,'request':request,'printer':job['printer']},sort_keys=True).encode()).hexdigest()
                await self.db('update', job['id'], status='ready', summary=summary, fingerprint=fingerprint)
        except asyncio.CancelledError:
            await self.db('update', job['id'], status='failed', error='Slicing interrupted. Prepare again.'); raise
        except Exception as exc:
            await self.db('update', job['id'], status='failed', error=str(exc) if isinstance(exc,ValueError) else 'Slicing failed. Check the worker runtime.')

    def require_idle(self, status):
        if not status.get('ready') or status.get('state') not in {'standby','complete','cancelled'}:
            raise ValueError('Printer must be connected, idle, and free of errors before starting.')

    async def start(self, job_id, confirmation):
        task = asyncio.create_task(self._start(job_id, confirmation)); self.operations.add(task)
        task.add_done_callback(self.operation_done)
        return await asyncio.shield(task)

    async def _start(self, job_id, confirmation):
        async with self.lock:
            job = await self.db('get', job_id)
            if job['status'] in ACTIVE or job['status'] == 'complete': return job
            if job['status'] != 'uploaded' or job.get('fingerprint') != confirmation.fingerprint:
                raise ValueError('The prepared print changed. Review it again.')
            settings = self.settings()
            if settings.profile_revision != job['printer']['profile_revision'] or job['summary'].get('profile_revision') != profile_revision():
                raise ValueError('The printer profile changed. Slice and review again.')
            for key in ['host','port','hostname','material','source','cfs_box','cfs_slot']:
                if getattr(settings,key) != job['printer'][key]:
                    raise ValueError('Printer or filament settings changed. Prepare a new print.')
            calibration = confirmation.calibration_test and max(job.get('size_mm',[999])) <= 30.01
            if not settings.profile_verified and not calibration:
                raise ValueError('First complete a supervised calibration print no larger than 30 mm, then verify its result.')
            if any(j['status'] in ACTIVE for j in await self.db('list')):
                raise ValueError('Another print is active or its start is unresolved. Check the printer first.')
            printer = self.printer_factory(settings)
            self.require_idle(await printer.status())
            slot = None
            if settings.source == 'cfs':
                slot = await printer.cfs_status()
                if slot['type'] != job['request']['material'] or slot.get('state') != 0:
                    raise ValueError('CFS material does not match, or the printer is busy. Check slot and material.')
            path = self.root / job_id / 'output/print.gcode'
            if path.is_symlink(): raise ValueError('Print file is invalid. Prepare again.')
            data = await asyncio.to_thread(path.read_bytes)
            if hashlib.sha256(data).hexdigest() != job['summary']['sha256']:
                raise ValueError('Print file changed after slicing. Prepare again.')
            filename = 'jarvis-' + job_id + '.gcode'
            await self.db('update', job_id, calibration_test=calibration)
            try:
                metadata = await printer.request('GET', '/server/files/metadata', params={'filename': filename})
                if metadata.get('size') != len(data):
                    raise ValueError('The uploaded file changed. Send the plate again.')
                self.require_idle(await printer.status())
                if settings.source == 'cfs':
                    fresh = await printer.cfs_status()
                    if fresh != slot: raise ValueError('CFS status changed during upload. Review the print again.')
            except Exception as exc:
                await self.db('update', job_id, status='ready', error=str(exc) if isinstance(exc,ValueError) else 'Upload verification failed; print was not started.')
                raise ValueError('Upload or readiness check failed; print was not started.') from None
            # Persist before sending. A disconnect must never cause an automatic repeat.
            await self.db('update', job_id, status='starting', started_at=time.time(), error=None)
            try:
                if slot: await printer.start_cfs(filename, slot)
                else: await printer.start(filename)
            except Exception:
                return await self.db('update', job_id, status='start_unknown', error='Start outcome is unknown. Check the printer; Jarvis will not resend it.')
            return await self.db('get', job_id)

    async def upload(self, job_id, fingerprint):
        task = asyncio.create_task(self._upload(job_id, fingerprint)); self.operations.add(task)
        task.add_done_callback(self.operation_done)
        return await asyncio.shield(task)

    async def _upload(self, job_id, fingerprint):
        async with self.lock:
            job = await self.db('get', job_id)
            if job['status'] in ACTIVE or job['status'] == 'complete':
                raise ValueError('This print is active or already complete.')
            if job['status'] not in {'ready', 'uploaded'} or job.get('fingerprint') != fingerprint:
                raise ValueError('Slice and review this plate before sending it.')
            settings = self.settings()
            if any(getattr(settings, k) != job['printer'][k] for k in ['host','port','hostname','material','source','cfs_box','cfs_slot']):
                raise ValueError('Printer settings changed. Slice the plate again.')
            if job['summary'].get('profile_revision') != profile_revision():
                raise ValueError('The slicer profile changed. Slice the plate again.')
            path = self.root / job_id / 'output/print.gcode'
            data = path.read_bytes()
            if path.is_symlink() or hashlib.sha256(data).hexdigest() != job['summary']['sha256']:
                raise ValueError('Print file changed after review. Slice again.')
            printer = self.printer_factory(settings)
            self.require_idle(await printer.status())
            filename = 'jarvis-' + job_id + '.gcode'
            await self.db('update', job_id, status='uploading', filename=filename)
            try:
                await printer.upload(filename, data)
            except Exception:
                await self.db('update', job_id, status='ready', error='Upload failed. Nothing was started.')
                raise
            return await self.db('update', job_id, status='uploaded', error=None)

    async def control(self, action, filename):
        async with self.lock:
            printer = self.printer_factory(self.settings()); status = await printer.status()
            if status.get('filename') != filename:
                raise ValueError('The printer’s current file changed. Refresh before controlling it.')
            allowed = {'pause':{'printing'},'resume':{'paused'},'cancel':{'printing','paused'}}
            if status['state'] not in allowed[action]: raise ValueError('Printer is not in the expected state.')
            await printer.control(action)
            return {'requested':action}

    async def resolve(self, job_id):
        async with self.lock:
            job = await self.db('get',job_id)
            if job['status'] not in ACTIVE: raise ValueError('This job does not need reconciliation.')
            self.require_idle(await self.printer_factory(self.settings()).status())
            return await self.db('update',job_id,status='canceled',error='Operator confirmed this print is no longer running. Prepare a new job to print again.')

    async def verify(self, job_id):
        async with self.lock:
            job = await self.db('get', job_id)
            if job['status'] != 'complete' or not job.get('calibration_test'):
                raise ValueError('Complete the calibration print and inspect it first.')
            settings = self.settings()
            if any(getattr(settings,k) != job['printer'][k] for k in ['host','port','hostname','material','source','cfs_box','cfs_slot']):
                raise ValueError('Printer settings changed since calibration.')
            settings.profile_verified = True
            expected_profile = profile_text({**job['request'],'source':job['printer']['source']})
            if job['summary'].get('profile_sha256') != hashlib.sha256(expected_profile.encode()).hexdigest():
                raise ValueError('The slicer profile changed since this test. Prepare a new calibration print.')
            settings.profile_revision = profile_revision()
            temp = self.root / 'settings.tmp'; temp.write_text(settings.model_dump_json(indent=2)); temp.replace(self.root / 'settings.json')
            return settings.model_dump()

    async def close(self):
        self.closed = True
        if self.monitor:
            self.monitor.cancel(); await asyncio.gather(self.monitor, return_exceptions=True)
        await asyncio.gather(*list(self.operations), return_exceptions=True)
        for task in self.tasks.values(): task.cancel()
        await asyncio.gather(*list(self.tasks.values()), return_exceptions=True)
        # Exiting the kiosk never cancels a physical print.


_service = None
def get_service():
    global _service
    if _service is None: _service = PrintService()
    return _service
