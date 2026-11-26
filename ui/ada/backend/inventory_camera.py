"""Bounded still capture: USB first, Raspberry Pi CSI camera second.

System camera tools avoid adding OpenCV or Pi-only wheels to the voice runtime.
No camera command is composed by a model and no shell is invoked.
"""
from __future__ import annotations

import io
from contextlib import nullcontext
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading

from PIL import Image, ImageOps

from .inventory import Input, get_inventory
from .projects import WorkspaceError, atomic_json
from .camera_csi import csi_lease
from pydantic import Field, field_validator

_capture_lock = threading.Lock()
_preview_stop = threading.Event()


class CameraSettings(Input):
    usb_device: str = ''
    width: int = Field(default=1920,ge=320,le=7680)
    height: int = Field(default=1080,ge=240,le=4320)
    rotation: int = 0

    @field_validator('usb_device')
    @classmethod
    def device(cls,value):
        if value and not re.fullmatch(r'/dev/(?:video\d+|v4l/by-id/[A-Za-z0-9_.:+-]+)',value):
            raise ValueError('Choose a USB video device from /dev.')
        return value

    @field_validator('rotation')
    @classmethod
    def orientation(cls,value):
        if value not in {0,90,180,270}:
            raise ValueError('Choose rotation 0, 90, 180 or 270.')
        return value


def settings():
    path=get_inventory().root/'camera.json'
    try:
        return CameraSettings.model_validate(json.loads(path.read_text()))
    except FileNotFoundError:
        return CameraSettings(usb_device=os.getenv('JARVIS_USB_CAMERA',''))


def save_settings(data):
    value=CameraSettings.model_validate(data)
    if value.width*value.height>25_000_000:
        raise WorkspaceError('Choose a capture resolution below 25 megapixels.')
    atomic_json(get_inventory().root/'camera.json',value.model_dump())
    return status()


def usb_devices():
    devices=[];seen=set()
    for path in sorted(Path('/dev/v4l/by-id').glob('*-video-index0')):
        target=str(path.resolve())
        if target not in seen:
            devices.append(str(path));seen.add(target)
    for entry in sorted(Path('/sys/class/video4linux').glob('video*')):
        # Pi codecs and ISP nodes also use /dev/videoN. Never classify them as USB.
        if '/usb' in str((entry/'device').resolve()):
            target='/dev/'+entry.name
            if target not in seen:
                devices.append(target);seen.add(target)
    return devices


def status():
    return {'settings':settings().model_dump(),'devices':usb_devices(),
            'usb_capture_installed':bool(shutil.which('fswebcam') or shutil.which('ffmpeg')),
            'pi_capture_installed':bool(shutil.which('rpicam-still') or shutil.which('libcamera-still')),
            'order':['USB','Pi ribbon camera']}


def normalise(data, rotation=0):
    if len(data)>20*1024*1024:
        raise WorkspaceError('The camera photograph exceeds 20 MB.')
    try:
        with Image.open(io.BytesIO(data)) as im:
            if im.width*im.height>25_000_000:
                raise WorkspaceError('The photograph exceeds 25 megapixels.')
            im=ImageOps.exif_transpose(im).convert('RGB')
            if rotation: im=im.rotate(-rotation,expand=True)
            output=io.BytesIO();im.save(output,format='JPEG',quality=95)
            return output.getvalue()
    except (OSError,ValueError,Image.DecompressionBombError):
        raise WorkspaceError('The camera did not produce a readable photograph.') from None


def capture():
    # A scan takes priority over the live view and needs exclusive camera access.
    _preview_stop.set()
    if not _capture_lock.acquire(timeout=4):
        raise WorkspaceError('The camera is already taking a photograph. Try again shortly.')
    try:
        config=settings();attempts=[]
        choices=list(dict.fromkeys(([config.usb_device] if config.usb_device else [])+usb_devices()))[:2]
        usb=shutil.which('fswebcam')
        ffmpeg=shutil.which('ffmpeg')
        pi=shutil.which('rpicam-still') or shutil.which('libcamera-still')
        with tempfile.TemporaryDirectory(prefix='ada-camera-') as directory:
            target=Path(directory)/'capture.jpg'
            commands=[]
            if usb:
                for device in choices:
                    commands.append(('USB',device,[usb,'--device',device,'--resolution',f'{config.width}x{config.height}',
                        '--skip','5','--no-banner','--jpeg','95',str(target)],12))
            elif ffmpeg:
                for device in choices:
                    for size in (['-video_size',f'{config.width}x{config.height}'],[]):
                        commands.append(('USB',device,[ffmpeg,'-hide_banner','-loglevel','error','-f','video4linux2',
                            *size,'-i',device,'-ss','1','-frames:v','1','-q:v','2','-y',str(target)],8))
            elif choices: attempts.append('USB capture needs fswebcam or ffmpeg.')
            if pi:
                commands.append(('Pi ribbon camera','CSI',[pi,'--nopreview','--timeout','1500',
                    '--width',str(config.width),'--height',str(config.height),'--output',str(target)],15))
            for source,device,command,timeout in commands:
                target.unlink(missing_ok=True)
                try:
                    with csi_lease() if source == 'Pi ribbon camera' else nullcontext():
                        subprocess.run(command,check=True,timeout=timeout,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
                    data=normalise(target.read_bytes(),config.rotation)
                    return data,{'source':source,'device':device,'fallback':source!='USB',
                                 'message':'Using the Pi ribbon camera because USB capture was unavailable.' if source!='USB' else 'Using the USB camera.'}
                except RuntimeError as error:
                    attempts.append(str(error))
                except (subprocess.SubprocessError,OSError,WorkspaceError):
                    attempts.append(f'{source} could not capture an image.')
        raise WorkspaceError('No camera could capture a photograph. Connect the USB or Pi camera and check camera setup. '+ ' '.join(dict.fromkeys(attempts)))
    finally:
        _capture_lock.release()
