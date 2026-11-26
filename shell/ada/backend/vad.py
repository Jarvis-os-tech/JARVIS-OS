"""Local speech classification assists UI feedback; Gemini owns turn boundaries."""
from __future__ import annotations

from array import array
from collections import deque
import math
import sys

import webrtcvad


class SpeechDetector:
    FRAME_BYTES = 640  # 20 ms, mono, PCM16 at 16 kHz.

    def __init__(self, silence_ms: int = 600) -> None:
        self.detector = webrtcvad.Vad(2)
        self.silence_frames = silence_ms // 20
        self.reset()

    def reset(self) -> None:
        self.pending = bytearray()
        self.window: deque[bool] = deque(maxlen=5)
        self.active = False
        self.silent = 0
        self.noise = 0.0015
        self.rms = 0.

    def feed(self, data: bytes) -> list[dict]:
        self.pending.extend(data)
        events = []
        while len(self.pending) >= self.FRAME_BYTES:
            frame = bytes(self.pending[:self.FRAME_BYTES])
            del self.pending[:self.FRAME_BYTES]
            samples = array("h", frame)
            if sys.byteorder != "little":
                samples.byteswap()
            rms = math.sqrt(sum(x * x for x in samples) / len(samples)) / 32768
            self.rms = rms
            classified = self.detector.is_speech(frame, 16000)
            voiced = classified and rms > max(0.002, self.noise * 2)
            if not classified and not self.active:
                self.noise = 0.98 * self.noise + 0.02 * min(rms, 0.02)
            self.window.append(voiced)
            if not self.active and len(self.window) == 5 and sum(self.window) >= 4:
                self.active = True
                self.silent = 0
                events.append({"type": "speech", "active": True})
            elif self.active:
                self.silent = 0 if voiced else self.silent + 1
                if self.silent >= self.silence_frames:
                    self.active = False
                    self.window.clear()
                    events.append({"type": "speech", "active": False})
        return events
