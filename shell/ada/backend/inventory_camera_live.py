"""Small MJPEG preview streams; never send preview frames to the vision model."""
import asyncio
from contextlib import suppress, ExitStack
from pathlib import Path
import shutil
import anyio

from . import inventory_camera as camera
from .projects import WorkspaceError


def commands(device):
    ffmpeg = shutil.which('ffmpeg')
    choices = [device] if device else camera.usb_devices()[:2]
    result = []
    if ffmpeg:
        for choice in choices:
            result.append([ffmpeg, '-hide_banner', '-loglevel', 'error', '-f', 'video4linux2',
                           '-video_size', '640x480', '-i', choice, '-an', '-vf', 'fps=8,scale=640:-2',
                           '-c:v', 'mjpeg', '-q:v', '5', '-f', 'image2pipe', 'pipe:1'])
    # An explicitly selected USB device must never silently display another camera.
    if not device:
        pi = shutil.which('rpicam-vid') or shutil.which('libcamera-vid')
        if pi:
            result.append([pi, '--nopreview', '--timeout', '0', '--width', '640', '--height', '480',
                           '--framerate', '8', '--codec', 'mjpeg', '--flush', '--output', '-'])
    return result


async def stop(process):
    if process.returncode is None:
        with suppress(ProcessLookupError):
            process.terminate()
        try:
            await asyncio.wait_for(process.wait(), 1)
        except TimeoutError:
            with suppress(ProcessLookupError):
                process.kill()
            await process.wait()


async def frames(device='', rotation=0):
    acquired = False
    # Allow the previous view a moment to release the camera during selection changes.
    for _ in range(20):
        acquired = camera._capture_lock.acquire(blocking=False)
        if acquired:
            break
        await asyncio.sleep(.1)
    if not acquired:
        raise WorkspaceError('The camera is busy. Try the live preview again after the scan finishes.')
    camera._preview_stop.clear()
    try:
        for command in commands(device):
            if camera._preview_stop.is_set():
                return
            process = None
            seen = False
            lease = ExitStack()
            try:
                if Path(command[0]).name in {'rpicam-vid', 'libcamera-vid'}:
                    try:
                        lease.enter_context(camera.csi_lease())
                    except RuntimeError as error:
                        raise WorkspaceError(str(error)) from None
                process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE,
                                                               stderr=asyncio.subprocess.DEVNULL)
                buffer = bytearray()
                deadline = asyncio.get_running_loop().time() + 8
                while not camera._preview_stop.is_set():
                    try:
                        chunk = await asyncio.wait_for(process.stdout.read(65536), .5)
                    except TimeoutError:
                        if asyncio.get_running_loop().time() > deadline:
                            break
                        continue
                    if not chunk:
                        break
                    buffer.extend(chunk)
                    if len(buffer) > 4 * 1024 * 1024:
                        break
                    while True:
                        start = buffer.find(b'\xff\xd8')
                        end = buffer.find(b'\xff\xd9', max(0, start + 2))
                        if start < 0 or end < 0:
                            break
                        frame = bytes(buffer[start:end+2])
                        del buffer[:end+2]
                        if rotation:
                            frame = await asyncio.to_thread(camera.normalise, frame, rotation)
                        seen = True
                        deadline = asyncio.get_running_loop().time() + 8
                        yield frame
                if seen:
                    return
            except OSError:
                pass
            finally:
                if process:
                    with anyio.CancelScope(shield=True):
                        await stop(process)
                lease.close()
        if not camera._preview_stop.is_set():
            raise WorkspaceError('Live preview unavailable. Check the selected camera and install ffmpeg for USB preview.')
    finally:
        camera._capture_lock.release()


def multipart(frame):
    return b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: ' + str(len(frame)).encode() + b'\r\n\r\n' + frame + b'\r\n'
