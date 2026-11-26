import time
import pytest
import numpy as np

from voice.fish_speaker import FishAudioClient, emotion_demo, has_emotion_cues, strip_cues


@pytest.mark.parametrize("request_text,cue", [
    ("Jarvis, laugh.", "[laughing]"),
    ("Please cry for me.", "[sobbing]"),
    ("Sound sad", "[sad]"),
    ("Sigh", "[sighing]"),
])
def test_emotion_demo(request_text, cue):
    assert emotion_demo(request_text).startswith(cue)
    assert emotion_demo("Why do people cry?") is None


def test_has_emotion_cues():
    assert has_emotion_cues("[warmly] Good morning, sir.") is True
    assert has_emotion_cues("Hello [small laugh] how are you?") is True
    assert has_emotion_cues("[thoughtful] It is an elegant approach.") is True
    assert has_emotion_cues("[sigh] System error detected.") is True
    assert has_emotion_cues("Ordinary plain text without brackets.") is False
    assert has_emotion_cues("") is False


def test_strip_cues():
    assert strip_cues("[warmly] Good morning, sir.") == "Good morning, sir."
    assert strip_cues("Hello [small laugh] sir [thoughtful] indeed.") == "Hello sir indeed."
    assert strip_cues("Plain text") == "Plain text"
    assert strip_cues("") == ""


def test_resample_to_24k():
    client = FishAudioClient(api_key="fake-key")
    # Generate 1 second of 44100 Hz mono int16 tone
    t = np.linspace(0, 1.0, 44100, endpoint=False)
    samples_44k = (np.sin(2 * np.pi * 440 * t) * 10000).astype(np.int16)
    pcm_44k = samples_44k.tobytes()

    pcm_24k = client._resample_to_24k(pcm_44k, 44100)
    # Output should have 24000 samples = 48000 bytes
    samples_24k = np.frombuffer(pcm_24k, dtype=np.int16)
    assert abs(len(samples_24k) - 24000) <= 2


def test_rate_limit_fallback_trigger():
    client = FishAudioClient(api_key="fake-key", cooldown_seconds=5.0)
    assert client.is_rate_limited is False

    # Simulate hitting rate limit
    client._rate_limited_until = time.monotonic() + 5.0
    assert client.is_rate_limited is True

    client.reset_cooldown()
    assert client.is_rate_limited is False


@pytest.mark.asyncio
async def test_synthesize_rate_limited_returns_none():
    client = FishAudioClient(api_key="fake-key", cooldown_seconds=10.0)
    client._rate_limited_until = time.monotonic() + 10.0
    res = await client.synthesize_pcm24k("[warmly] Test")
    assert res is None


@pytest.mark.asyncio
async def test_fallback_flow_on_rate_limit():
    raw_prompt = "[warmly] Hello sir, [small laugh] how are you?"
    client = FishAudioClient(api_key="fake-key", cooldown_seconds=60.0)
    client._rate_limited_until = time.monotonic() + 60.0

    # Primary emotional synth attempt
    pcm = await client.synthesize_pcm24k(raw_prompt)
    assert pcm is None  # Fails due to rate limit cooldown

    # Fallback to stripped text for Gemini Live
    clean_prompt = strip_cues(raw_prompt)
    assert clean_prompt == "Hello sir, how are you?"



async def _inline_request(function, *args):
    return function(*args)


@pytest.mark.asyncio
async def test_numbered_keys_skip_rejected_credentials_and_send_model_header(monkeypatch):
    import io
    import urllib.error
    import wave

    monkeypatch.setenv("FISH_AUDIO_API_KEY", "demo-expired")
    monkeypatch.setenv("FISH_AUDIO_API_KEY_1", "demo-expired")
    monkeypatch.setenv("FISH_AUDIO_API_KEY_3", "demo-active")
    monkeypatch.setenv("FISH_AUDIO_MODEL", "drama-3")
    attempts = []
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
        audio.writeframes(b"\x01\x00")

    def request(req, timeout):
        attempts.append(req.get_header("Authorization"))
        assert req.get_header("Model") == "drama-3"
        if attempts[-1] == "Bearer demo-expired":
            raise urllib.error.HTTPError(req.full_url, 401, "Expired", {}, None)
        response = io.BytesIO(output.getvalue())
        response.status = 200
        return response

    monkeypatch.setattr("asyncio.to_thread", _inline_request)
    monkeypatch.setattr("urllib.request.urlopen", request)
    client = FishAudioClient()
    assert await client.synthesize_pcm24k("Hello") == b"\x01\x00"
    assert await client.synthesize_pcm24k("Again") == b"\x01\x00"
    assert attempts == ["Bearer demo-expired", "Bearer demo-active", "Bearer demo-active"]


@pytest.mark.asyncio
async def test_rate_limit_respects_retry_after_without_trying_other_keys(monkeypatch):
    import urllib.error

    monkeypatch.setenv("FISH_AUDIO_API_KEY", "demo-primary")
    monkeypatch.setenv("FISH_AUDIO_API_KEY_1", "demo-secondary")
    attempts = []

    def request(req, timeout):
        attempts.append(req.get_header("Authorization"))
        raise urllib.error.HTTPError(req.full_url, 429, "Limit", {"Retry-After": "120"}, None)

    monkeypatch.setattr("asyncio.to_thread", _inline_request)
    monkeypatch.setattr("urllib.request.urlopen", request)
    client = FishAudioClient(cooldown_seconds=5)
    assert await client.synthesize_pcm24k("Hello") is None
    assert client._rate_limited_until - time.monotonic() > 110
    assert await client.synthesize_pcm24k("Again") is None
    assert attempts == ["Bearer demo-primary"]
