"""Cross-process ownership of the Pi ribbon camera; USB cameras are independent."""
from contextlib import contextmanager
import fcntl
from pathlib import Path

LOCK = Path(__file__).resolve().parents[1] / 'data' / 'gestures' / 'camera.lock'


@contextmanager
def csi_lease():
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    with LOCK.open('a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('The Pi ribbon camera is in use. Pause gesture control or close its camera preview first.') from None
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def select_csi_camera(cameras):
    """Picamera2 also lists UVC devices. Never select one, including RealSense."""
    for camera in cameras:
        identifier = str(camera.get('Id', ''))
        if identifier.startswith('/base/') and '/usb' not in identifier.lower():
            return camera
    raise RuntimeError('No Pi ribbon camera found. Check the CSI cable and restart Ada. USB cameras are not used for gestures.')
