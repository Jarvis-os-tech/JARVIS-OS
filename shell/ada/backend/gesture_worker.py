"""Native CSI + Hailo process. stdout is JSON only; never writes camera images."""
import argparse
from contextlib import ExitStack, redirect_stdout
import json
from pathlib import Path
import signal
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def emit(message):
    print(json.dumps(message, allow_nan=False, separators=(',', ':')), flush=True)


def run(args):
    # Native libraries must come from system Python, separate from Ada's venv.
    with redirect_stdout(sys.stderr):
        import cv2
        from picamera2 import Picamera2
        from picamera2.devices import Hailo
        from libcamera import controls
        from backend.camera_csi import csi_lease, select_csi_camera
        from backend.gesture_vision import HandTracker
    cv2.setNumThreads(1)
    stopped = False

    def stop(*_):
        nonlocal stopped
        stopped = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    with ExitStack() as stack:
        stack.enter_context(csi_lease())
        info = select_csi_camera(Picamera2.global_camera_info())
        with redirect_stdout(sys.stderr):
            palm = stack.enter_context(Hailo(str(args.models / 'palm_detection_lite.hef')))
            landmark = stack.enter_context(Hailo(str(args.models / 'hand_landmark_lite.hef')))
        tracker = HandTracker(palm, landmark, args.hand)
        camera = Picamera2(info['Num'])
        stack.callback(camera.close)
        # Picamera2's BGR888 yields RGB bytes (libcamera's pixel-format naming).
        config = camera.create_video_configuration(main={'size': (640, 480), 'format': 'BGR888'},
                                                   controls={'FrameRate': 30}, buffer_count=4, queue=False)
        camera.configure(config)
        if 'AfMode' in camera.camera_controls:
            camera.set_controls({'AfMode': controls.AfModeEnum.Continuous})
        camera.start()
        stack.callback(camera.stop)
        emit({'type': 'ready', 'source': 'csi', 'camera': info['Model'], 'accelerator': 'Hailo-8'})
        start = time.monotonic()
        frames = 0
        while not stopped and (not args.seconds or time.monotonic() - start < args.seconds):
            began = time.monotonic()
            frame = camera.capture_array('main')
            if args.rotation:
                frame = cv2.rotate(frame, {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180,
                                          270: cv2.ROTATE_90_COUNTERCLOCKWISE}[args.rotation])
            inference = time.monotonic()
            sample = tracker.infer(frame)
            frames += 1
            sample.update(type='frame', seq=frames, timestamp=time.monotonic(),
                          inference_ms=round((time.monotonic() - inference) * 1000, 1),
                          fps=round(frames / max(time.monotonic() - start, .001), 1))
            emit(sample)
            time.sleep(max(0, 1 / 30 - (time.monotonic() - began)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--models', type=Path, default=ROOT / 'data/gestures/models')
    parser.add_argument('--hand', choices=['any', 'left', 'right'], default='any')
    parser.add_argument('--rotation', type=int, choices=[0, 90, 180, 270], default=0)
    parser.add_argument('--seconds', type=float, default=0)
    try:
        run(parser.parse_args())
    except BrokenPipeError:
        pass
    except Exception as error:
        import traceback
        traceback.print_exc(file=sys.stderr)
        emit({'type': 'error', 'message': f'Gesture tracking stopped: {error}. Check data/logs/gestures.log.'})
        sys.exit(1)
