"""Moonraker access to one explicitly configured local printer."""
import asyncio
import os
import time
import json
import httpx
import websockets


class PrinterError(ValueError):
    pass


class Printer:
    def __init__(self, settings):
        self.settings = settings

    async def request(self, method, path, **kwargs):
        if not self.settings.host:
            raise PrinterError('Set the printer IP in Printing settings.')
        headers = {}
        if os.getenv('JARVIS_PRINTER_API_KEY'):
            headers['X-Api-Key'] = os.environ['JARVIS_PRINTER_API_KEY']
        try:
            async with httpx.AsyncClient(base_url=f'http://{self.settings.host}:{self.settings.port}',
                    headers=headers, trust_env=False, follow_redirects=False,
                    timeout=httpx.Timeout(8, read=90 if path.endswith('/upload') else 8)) as client:
                response = await client.request(method, path, **kwargs)
                response.raise_for_status()
                body = response.json()
                if 'error' in body:
                    raise PrinterError('The printer rejected the request. Check its screen.')
                return body.get('result', body)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (401, 403):
                raise PrinterError('Printer authorization is required; configure JARVIS_PRINTER_API_KEY on the backend.') from None
            raise PrinterError(f'Printer request failed (HTTP {exc.response.status_code}). Check its screen.') from None
        except (httpx.HTTPError, ValueError) as exc:
            if isinstance(exc, PrinterError):
                raise
            raise PrinterError('Could not reach the printer. Check its power, Wi-Fi, and IP address.') from None

    async def status(self):
        info, result = await asyncio.gather(
            self.request('GET', '/printer/info'),
            self.request('GET', '/printer/objects/query?print_stats&virtual_sdcard&extruder&heater_bed&pause_resume&webhooks&configfile'))
        s = result['status']; stats = s.get('print_stats', {}); sd = s.get('virtual_sdcard', {})
        state = stats.get('state', 'unknown')
        if s.get('pause_resume', {}).get('is_paused'):
            state = 'paused'
        elif sd.get('is_active'):
            state = 'printing'
        connected = info.get('state') == 'ready' and s.get('webhooks', {}).get('state') == 'ready'
        identity_ok = not self.settings.hostname or self.settings.hostname == info.get('hostname')
        config = s.get('configfile', {})
        extruder_config = config.get('settings', config.get('config', {})).get('extruder', {})
        nozzle = extruder_config.get('nozzle_diameter', s.get('extruder', {}).get('nozzle_diameter', 0))
        nozzle_ok = abs(float(nozzle) - .4) < .001
        message = ('The printer identity does not match the configured K2.' if not identity_ok else
                   'Could not verify a 0.4 mm nozzle in the printer configuration.' if not nozzle_ok else
                   stats.get('message') or info.get('state_message', ''))
        return {'connected': True, 'ready': connected and identity_ok and nozzle_ok,
                'hostname': info.get('hostname'), 'identity_ok': identity_ok, 'nozzle_ok': nozzle_ok,
                'state': state, 'filename': stats.get('filename', ''),
                'progress': round(max(0, min(1, sd.get('progress', 0))) * 100, 1),
                'elapsed_seconds': stats.get('print_duration', 0),
                'nozzle': s.get('extruder', {}).get('temperature'),
                'bed': s.get('heater_bed', {}).get('temperature'),
                'nozzle_target': s.get('extruder', {}).get('target', 0),
                'bed_target': s.get('heater_bed', {}).get('target', 0),
                'message': message, 'checked_at': time.time()}

    async def upload(self, name, data):
        result = await self.request('POST', '/server/files/upload',
            data={'root': 'gcodes', 'print': 'false'}, files={'file': (name, data, 'application/octet-stream')})
        item = result.get('item', {})
        if item.get('path') != name or item.get('root') != 'gcodes' or ('size' in item and item['size'] != len(data)):
            raise PrinterError('Printer did not confirm the complete uploaded file. Print was not started.')
        metadata = await self.request('GET', '/server/files/metadata', params={'filename': name})
        if metadata.get('size') != len(data):
            raise PrinterError('Uploaded file metadata does not match. Print was not started.')
        return name

    async def start(self, filename):
        return await self.request('POST', '/printer/print/start', json={'filename': filename})

    async def cfs_status(self):
        try:
            snapshot = {}
            async with websockets.connect(f'ws://{self.settings.host}:9999', proxy=None,
                    open_timeout=5, close_timeout=2, max_size=2**20) as ws:
                await ws.send(json.dumps({'method':'get','params':{'boxsInfo':1}}))
                async with asyncio.timeout(8):
                    while True:
                        raw = await ws.recv()
                        if raw == 'heart_beat':
                            await ws.send('ok'); continue
                        data = json.loads(raw)
                        if isinstance(data,dict): snapshot.update(data)
                        if 'boxsInfo' in snapshot and 'state' in snapshot:
                            boxes = snapshot['boxsInfo'].get('materialBoxs', [])
                            box = next((b for b in boxes if b.get('type') == 0 and b.get('id') == self.settings.cfs_box), None)
                            slot = next((s for s in (box or {}).get('materials', []) if s.get('id') == self.settings.cfs_slot-1), None)
                            if not box or not slot or box.get('state') != 1 or slot.get('state') != 1:
                                raise PrinterError('Selected CFS slot is not available. Check the printer screen.')
                            return {'box_id':box['id'], 'material_id':slot['id'], 'type':slot.get('type'),
                                    'color':slot.get('color'), 'name':slot.get('name'), 'state':snapshot['state']}
        except (OSError, TimeoutError, websockets.exceptions.WebSocketException, ValueError) as exc:
            if isinstance(exc, PrinterError): raise
            raise PrinterError('Could not verify the CFS slot. Check the printer connection.') from None

    async def start_cfs(self, filename, slot):
        # The stock launcher configures CFS before starting; plain Moonraker start
        # bypasses that step. Shapes come from Creality Print's DeviceInterface.
        roots = await self.request('GET', '/server/files/roots')
        root = next((r['path'] for r in roots if r.get('name') == 'gcodes'), None)
        if not root or not root.startswith('/'):
            raise PrinterError('Printer did not report its G-code directory.')
        path = root.rstrip('/') + '/' + filename
        mapping = {'id':'T1A', 'type':slot['type'], 'color':slot['color'],
                   'boxId':slot['box_id'], 'materialId':slot['material_id']}
        async with websockets.connect(f'ws://{self.settings.host}:9999', proxy=None,
                open_timeout=5, close_timeout=2, max_size=2**20) as ws:
            await ws.send(json.dumps({'method':'set','params':{'colorMatch':{'path':path,'list':[mapping]}}}))
            # Same ordered connection as the vendor client. Never retry a start.
            await ws.send(json.dumps({'method':'set','params':{'multiColorPrint':{'gcode':path,'enableSelfTest':1}}}))

    async def control(self, action):
        if action not in ('pause', 'resume', 'cancel'):
            raise PrinterError('Unknown printer action.')
        return await self.request('POST', '/printer/print/' + action)
