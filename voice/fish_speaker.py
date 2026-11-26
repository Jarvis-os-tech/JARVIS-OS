"""Fish Audio client with emotional cue detection, 24kHz resampling, and automatic rate-limit fallback."""

from __future__ import annotations

import asyncio
import io
import json
import logging
import math
import os
import re
import time
import urllib.error
import urllib.request
import wave
from typing import Optional

import numpy as np
import scipy.signal

log = logging.getLogger("jarvis.fish_speaker")

EMOTION_CUES_PATTERN = re.compile(r"\[[a-zA-Z0-9\s,_\.\-\'\"]+\]")
KNOWN_EMOTION_HINTS = (
    "warmly", "softly", "sigh", "small laugh", "laughing", "whispering",
    "thoughtful", "smiling", "amused", "curious", "gentle", "calm", "giggle"
)


def has_emotion_cues(text: str) -> bool:
    """Check if the text contains bracketed performance cues like [warmly] or [small laugh]."""
    if not text or "[" not in text or "]" not in text:
        return False
    matches = EMOTION_CUES_PATTERN.findall(text)
    if not matches:
        return False
    for m in matches:
        inner = m.strip("[]").strip().lower()
        if any(hint in inner for hint in KNOWN_EMOTION_HINTS) or len(inner.split()) <= 4:
            return True
    return False


def strip_cues(text: str) -> str:
    """Strip bracketed performance cues so fallback engines (like Gemini Live) do not read them literally."""
    if not text:
        return ""
    cleaned = EMOTION_CUES_PATTERN.sub(" ", text)
    return re.sub(r"\s+", " ", cleaned).strip()


def emotion_demo(user_text: str) -> str | None:
    """Map explicit voice-demo requests to Fish performance cues."""
    request = re.fullmatch(
        r"(?:jarvis[, ]+)?(?:please )?(?:laugh|cry|sound sad|sigh)(?: for me)?[.!?]*",
        user_text.strip(), re.IGNORECASE,
    )
    if not request:
        return None
    command = re.sub(r"^(?:jarvis[, ]+)?(?:please )?", "", request[0].lower())
    command = command.rstrip(".!?").removesuffix(" for me")
    return {
        "laugh": "[laughing] Ha, ha, ha!",
        "cry": "[sobbing] I thought I could hold it together.",
        "sound sad": "[sad] I wish things had turned out differently.",
        "sigh": "[sighing] Ah.",
    }[command]


class FishAudioClient:
    """Fish Audio client for high-fidelity emotional speech with rate-limit tracking and fallback."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "s2.1-pro",
        base_url: str = "https://api.fish.audio",
        cooldown_seconds: float = 60.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = os.environ.get("FISH_AUDIO_MODEL") or model
        self.reference_id = os.environ.get("FISH_AUDIO_REFERENCE_ID", "").strip()
        self.cooldown_seconds = cooldown_seconds
        self._explicit_key = api_key
        self._rejected_keys: set[str] = set()
        self._rate_limited_until: float = 0.0
        self._last_error: Optional[str] = None

    def _available_keys(self) -> list[str]:
        values = [self._explicit_key] if self._explicit_key else [
            os.environ.get(name)
            for name in ("FISH_AUDIO_API_KEY", *(f"FISH_AUDIO_API_KEY_{index}" for index in range(1, 21)),
                         "FISH_API_KEY")
        ]
        keys = (value.strip().strip("\"'") for value in values if value)
        return list(dict.fromkeys(key for key in keys if key and not key.startswith("PASTE_")
                                  and key not in self._rejected_keys))

    @property
    def api_key(self) -> str:
        return next(iter(self._available_keys()), "")

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    @property
    def is_rate_limited(self) -> bool:
        return time.monotonic() < self._rate_limited_until

    def reset_cooldown(self) -> None:
        self._rate_limited_until = 0.0
        self._last_error = None
        self._rejected_keys.clear()

    def _resample_to_24k(self, pcm_bytes: bytes, in_rate: int) -> bytes:
        """Resample mono 16-bit PCM audio to 24000 Hz for JARVIS's native playback engine."""
        if in_rate == 24000:
            return pcm_bytes
        samples = np.frombuffer(pcm_bytes, dtype=np.int16)
        if len(samples) == 0:
            return b""
        if in_rate == 44100:
            # 24000 / 44100 = 80 / 147
            up, down = 80, 147
        elif in_rate == 48000:
            # 24000 / 48000 = 1 / 2
            up, down = 1, 2
        elif in_rate == 16000:
            # 24000 / 16000 = 3 / 2
            up, down = 3, 2
        else:
            g = math.gcd(24000, in_rate)
            up, down = 24000 // g, in_rate // g

        resampled = scipy.signal.resample_poly(samples, up, down).astype(np.int16)
        return resampled.tobytes()

    async def synthesize_pcm24k(
        self,
        text: str,
        model: Optional[str] = None,
        timeout: float = 15.0,
    ) -> Optional[bytes]:
        """Synthesize text to 24 kHz mono PCM16.
        
        Returns:
            bytes: 24kHz mono PCM16 audio bytes on success.
            None: If rate limited, unconfigured, or on error (signals fallback).
        """
        if not text or not text.strip():
            return None

        if not self.is_configured:
            log.debug("Fish Audio not configured (missing key); falling back")
            return None

        if self.is_rate_limited:
            remaining = int(self._rate_limited_until - time.monotonic())
            log.warning("Fish Audio is rate-limited (cooling down, %ds remaining); falling back", remaining)
            return None

        clean_prompt = text.strip()
        target_model = model or self.model

        def _do_request(key: str, remaining: float) -> tuple[int, bytes, str | None]:
            url = f"{self.base_url}/v1/tts"
            body = {"text": clean_prompt, "format": "wav", "sample_rate": 24000}
            if self.reference_id:
                body["reference_id"] = self.reference_id
            payload = json.dumps(body).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=payload,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "model": target_model,
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=remaining) as resp:
                    return resp.status, resp.read(), None
            except urllib.error.HTTPError as exc:
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                exc.close()
                return exc.code, b"", retry_after
            except OSError:
                return -1, b"", None

        deadline = time.monotonic() + timeout
        status_code, body, retry_after = -1, b"", None
        for key in self._available_keys():
            remaining = deadline - time.monotonic()
            if remaining <= 0 or self.is_rate_limited:
                return None
            status_code, body, retry_after = await asyncio.to_thread(_do_request, key, remaining)
            if status_code not in (401, 403):
                break
            self._rejected_keys.add(key)

        if status_code == 200 and body:
            try:
                with wave.open(io.BytesIO(body), "rb") as wf:
                    channels = wf.getnchannels()
                    sampwidth = wf.getsampwidth()
                    rate = wf.getframerate()
                    frames = wf.readframes(wf.getnframes())

                if channels > 1:
                    raw_samples = np.frombuffer(frames, dtype=np.int16)
                    frames = raw_samples.reshape(-1, channels).mean(axis=1).astype(np.int16).tobytes()

                pcm_24k = self._resample_to_24k(frames, rate)
                self._last_error = None
                log.info("Fish Audio synthesized %d bytes at 24 kHz", len(pcm_24k))
                return pcm_24k
            except Exception as parse_err:
                log.warning("Failed parsing Fish Audio WAV stream: %s", parse_err)
                return None

        if status_code == 429:
            cooldown = self.cooldown_seconds
            if retry_after and len(retry_after) <= 10 and retry_after.isascii() and retry_after.isdigit():
                cooldown = max(cooldown, int(retry_after))
            self._rate_limited_until = time.monotonic() + cooldown
            self._last_error = "Rate limited (429)"
            log.warning("Fish Audio rate limited; using fallback during cooldown")
            return None

        self._last_error = f"HTTP {status_code}"
        log.warning("Fish Audio synthesis unavailable (status=%d); using fallback", status_code)
        return None

    async def stream_pcm24k(self, text: str, on_chunk, timeout: float = 15.0) -> bool:
        """Stream Fish PCM chunks to ``on_chunk`` using Fish's native WebSocket API."""
        if not text.strip() or not self.is_configured or self.is_rate_limited:
            return False
        try:
            import msgpack
            import websockets
        except ImportError:
            log.warning("Fish streaming test needs msgpack and websockets")
            return False
        request = {"text": "", "format": "pcm", "sample_rate": 24000,
                   "chunk_length": 100, "latency": "low"}
        if self.reference_id:
            request["reference_id"] = self.reference_id
        deadline = time.monotonic() + timeout
        for key in self._available_keys():
            try:
                headers = {"Authorization": f"Bearer {key}", "model": self.model}
                async with websockets.connect(f"{self.base_url.replace('https://', 'wss://')}/v1/tts/live",
                                              additional_headers=headers,
                                              open_timeout=max(1, deadline - time.monotonic())) as socket:
                    await socket.send(msgpack.packb({"event": "start", "request": request}, use_bin_type=True))
                    await socket.send(msgpack.packb({"event": "text", "text": text.strip()}, use_bin_type=True))
                    await socket.send(msgpack.packb({"event": "flush"}, use_bin_type=True))
                    await socket.send(msgpack.packb({"event": "stop"}, use_bin_type=True))
                    async for raw in socket:
                        event = msgpack.unpackb(raw, raw=False)
                        if event.get("event") == "audio" and isinstance(event.get("audio"), bytes):
                            chunk = event["audio"]
                            if chunk and len(chunk) % 2 == 0:
                                await on_chunk(chunk)
                        elif event.get("event") == "finish":
                            return event.get("reason") == "stop"
                    return False
            except Exception as error:
                log.warning("Fish streaming attempt failed: %s", type(error).__name__)
                status = getattr(getattr(error, "response", None), "status_code", None)
                if status in (401, 403):
                    self._rejected_keys.add(key)
                    continue
                if status == 429:
                    self._rate_limited_until = time.monotonic() + self.cooldown_seconds
                return False
        return False
