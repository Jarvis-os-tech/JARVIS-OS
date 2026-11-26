"""One browser owns the CSI tracking worker; disconnect always releases hardware."""
import asyncio
from contextlib import suppress
import json
import os
import time
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict, ValidationError

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / 'data/gestures/models'
router = APIRouter()
owner = asyncio.Lock()


class TrackingOptions(BaseModel):
    model_config = ConfigDict(extra='forbid')
    hand: Literal['any', 'left', 'right'] = 'any'
    rotation: Literal[0, 90, 180, 270] = 0


@router.get('/api/gestures/status')
def status():
    models = all((MODELS / name).is_file() for name in ('palm_detection_lite.hef', 'hand_landmark_lite.hef'))
    return {'source': 'csi', 'camera': 'Raspberry Pi ribbon camera', 'accelerator': 'Hailo-8',
            'models_installed': models, 'busy': owner.locked()}


async def stop_worker(process):
    if process.returncode is None:
        with suppress(ProcessLookupError):
            process.terminate()
        try:
            await asyncio.wait_for(process.wait(), 1)
        except TimeoutError:
            with suppress(ProcessLookupError):
                process.kill()
            await process.wait()


async def forward_frames(process, socket):
    ready = False
    while True:
        # A stalled capture/inference must never leave a held gesture active.
        line = await asyncio.wait_for(process.stdout.readline(), 6 if ready else 25)
        if not line:
            raise RuntimeError('The camera tracking process ended. Check data/logs/gestures.log.')
        event = json.loads(line)
        if event.get('type') == 'ready':
            ready = True
        if event.get('type') == 'frame' and time.monotonic() - event['timestamp'] > .25:
            continue
        await asyncio.wait_for(socket.send_json(event), 2)
        if event.get('type') == 'error':
            return


async def watch_disconnect(socket):
    while True:
        event = await socket.receive()
        if event['type'] == 'websocket.disconnect':
            return
        # Configuration changes use a fresh connection; no unbounded inbound work.
        if event.get('text') == 'stop':
            return


@router.websocket('/ws/gestures')
async def gestures(socket: WebSocket):
    origin = socket.headers.get('origin')
    if not origin or urlparse(origin).netloc != socket.headers.get('host'):
        await socket.close(code=1008)
        return
    await socket.accept()
    # A changed hand/orientation immediately reconnects. Allow the previous
    # socket's worker a bounded interval to release the CSI camera and NPU.
    try:
        await asyncio.wait_for(owner.acquire(), 4)
    except TimeoutError:
        await socket.send_json({'type': 'error', 'message': 'Gesture control is already open in another window.'})
        await socket.close(code=1013)
        return
    try:
        process = None
        tasks = []
        try:
            options = TrackingOptions.model_validate(await asyncio.wait_for(socket.receive_json(), 5))
            if not status()['models_installed']:
                raise RuntimeError('Gesture models are missing. Run python3 scripts/setup_gestures.py.')
            logs = ROOT / 'data/logs'
            logs.mkdir(parents=True, exist_ok=True)
            with (logs / 'gestures.log').open('ab') as log:
                process = await asyncio.create_subprocess_exec(
                    '/usr/bin/python3', '-u', str(ROOT / 'backend/gesture_worker.py'),
                    '--hand', options.hand, '--rotation', str(options.rotation), '--models', str(MODELS),
                    cwd=ROOT, stdout=asyncio.subprocess.PIPE, stderr=log, limit=65536,
                    env={**os.environ, 'HAILORT_LOGGER_PATH': str(logs)})
                tasks = [asyncio.create_task(forward_frames(process, socket)),
                         asyncio.create_task(watch_disconnect(socket))]
                done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    task.result()
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass
        except (TimeoutError, ValidationError, ValueError, RuntimeError, OSError) as error:
            message = str(error) or 'Gesture tracking timed out. Check the ribbon camera and try again.'
            with suppress(Exception):
                await asyncio.wait_for(socket.send_json({'type': 'error', 'message': message}), 1)
        finally:
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            if process:
                await stop_worker(process)
            with suppress(Exception):
                await socket.close()
    finally:
        owner.release()
