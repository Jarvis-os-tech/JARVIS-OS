"""Opt-in audio transport diagnostics, without recordings or transcript text."""
from __future__ import annotations

import json
import logging
import os
import time
import uuid

logger = logging.getLogger("uvicorn.error.jarvis.audio")


class AudioTrace:
    def __init__(self):
        self.enabled = os.getenv("JARVIS_DEBUG", "").lower() in {"1", "true", "yes"}
        self.session = uuid.uuid4().hex[:8]
        self.started = time.monotonic()
        self.received = self.sent = self.output_bytes = 0
        self.peak_rms = 0.
        self.last_gemini = None
        self.audio_turn = None

    def log(self, event, **values):
        if self.enabled:
            logger.info("[Jarvis audio] %s", json.dumps({
                "session": self.session, "elapsed_s": round(time.monotonic() - self.started, 2),
                "event": event, **values,
            }))

    def observe(self, event):
        if not self.enabled:
            return
        if isinstance(event, bytes):
            self.output_bytes += max(0, len(event) - 12)
            if self.audio_turn is not None:
                self.log("response_audio", epoch=self.audio_turn[0], turn=self.audio_turn[1])
                self.audio_turn = None
            return
        kind = event.get("type")
        if kind == "transcript":
            self.log("speech_recognized" if event.get("role") == "user" else "response_text",
                     characters=len(event.get("text", "")), epoch=event.get("epoch"), turn=event.get("turn"))
        elif kind == "speech":
            self.log("local_speech_start" if event.get("active") else "local_speech_end")
        elif kind in {"connecting", "ready", "reconnecting", "turn_started", "interrupted", "generation_complete", "turn_complete", "waiting"}:
            self.log(kind, epoch=event.get("epoch"), turn=event.get("turn"))
            if kind == "turn_started":
                self.audio_turn = (event.get("epoch"), event.get("turn"))
        elif kind == "error":
            self.log("error", code=event.get("code"), retryable=event.get("retryable"))

    def snapshot(self, *, ready, muted, queued, dropped):
        self.log("transport", ready=ready, muted=muted, microphone_frames=self.received,
                 gemini_frames=self.sent, queued_frames=queued, dropped_frames=dropped,
                 microphone_peak_rms=round(self.peak_rms, 5),
                 output_seconds=round(self.output_bytes / 48000, 2),
                 last_gemini_seconds=None if self.last_gemini is None else round(time.monotonic() - self.last_gemini, 1))
        self.peak_rms = 0.
