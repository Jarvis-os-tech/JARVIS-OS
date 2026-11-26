"""Local HTTP application and a single-owner voice WebSocket."""
from __future__ import annotations

import asyncio
import os
import signal
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .config import ROOT, VOICES, InstructionsUpdate, Settings, VoiceSelection, api_key, preferences_configured, read_default_instructions, read_settings, reset_instructions, save_instructions, save_settings, save_voice
from .config import AudioPreferencesUpdate, save_audio_preferences
from .live import LiveBridge
from .project_routes import router as project_router
from .projects import store
from .inventory import get_inventory
from .inventory_routes import router as inventory_router
from .gesture_routes import router as gesture_router
from .printing.routes import router as printing_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # A launch begins at the welcome screen. Reloads and voice reconnects within
    # this launch keep the current selection; all saved project content persists.
    await asyncio.to_thread(store.activate, None)
    await asyncio.to_thread(get_inventory().recover_scans)
    from .cad import recover
    await asyncio.to_thread(recover)
    from .printing.service import get_service as printing_service
    await printing_service().recover()
    try:
        yield
    finally:
        await printing_service().close()


app = FastAPI(title="ADA Jarvis", docs_url=None, redoc_url=None, lifespan=lifespan)
if os.environ.get("JARVIS_HOST", "127.0.0.1") in {"localhost", "127.0.0.1", "::1"}:
    # The local kiosk accepts requests addressed to loopback, including WebSockets.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]"], www_redirect=False)
app.include_router(project_router)
app.include_router(inventory_router)
app.include_router(gesture_router)
app.include_router(printing_router)
voice_owner = asyncio.Lock()


def same_origin(origin: str | None, host: str | None) -> bool:
    return bool(origin and host and urlparse(origin).netloc == host)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = "microphone=(self), camera=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; "
        "connect-src 'self' ws: wss:; worker-src 'self'; object-src 'none'; frame-ancestors 'none'"
    )
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    elif request.url.path.startswith("/static/"):
        # HTML and its module graph must be from the same release. Chromium can
        # otherwise reuse heuristically cached scripts in the persistent kiosk.
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/api/health")
async def health():
    return {"ok": True, "configured": bool(api_key()), "busy": voice_owner.locked(), "pid": os.getpid()}


@app.post("/api/exit")
async def exit_app(request: Request):
    if not same_origin(request.headers.get("origin"), request.headers.get("host")):
        raise HTTPException(403, "Exit must be requested from Jarvis.")
    kiosk = os.environ.get("JARVIS_KIOSK_SESSION") == "1"
    if kiosk:
        # Let the response reach the browser, then the launcher cleans up both processes.
        asyncio.get_running_loop().call_later(.3, os.kill, os.getpid(), signal.SIGTERM)
    return {"kiosk": kiosk}


@app.get("/api/settings")
async def get_settings():
    try:
        return {"settings": read_settings().model_dump(), "configured": bool(api_key()),
                "preferences_configured": preferences_configured(), "voices": VOICES,
                "default_instructions": read_default_instructions()}
    except ValueError:
        raise HTTPException(422, "Invalid local configuration; check data/settings.json.") from None


@app.post("/api/settings")
async def put_settings(settings: Settings, request: Request):
    if not same_origin(request.headers.get("origin"), request.headers.get("host")):
        raise HTTPException(403, "Settings must be saved from Jarvis.")
    if voice_owner.locked():
        raise HTTPException(409, "Close the active conversation before changing configuration.")
    save_settings(settings)
    return await get_settings()


@app.patch("/api/settings/voice")
async def put_voice(selection: VoiceSelection, request: Request):
    if not same_origin(request.headers.get("origin"), request.headers.get("host")):
        raise HTTPException(403, "Settings must be saved from Jarvis.")
    # A running bridge keeps its own Settings snapshot. The selecting browser
    # reconnects after this save; the next bridge reads the new voice.
    try:
        save_voice(selection)
    except ValueError:
        raise HTTPException(422, "Invalid local configuration; check data/settings.json.") from None
    except OSError:
        raise HTTPException(500, "Could not save the voice. Check local file permissions.") from None
    return await get_settings()


@app.patch("/api/settings/instructions")
async def put_instructions(update: InstructionsUpdate, request: Request):
    return await change_instructions(request, lambda: save_instructions(update))


@app.patch('/api/settings/audio')
async def put_audio_preferences(update: AudioPreferencesUpdate, request: Request):
    return await change_instructions(request, lambda: save_audio_preferences(update))


@app.patch("/api/settings/instructions/default")
async def put_default_instructions(update: InstructionsUpdate, request: Request):
    return await change_instructions(request, lambda: save_instructions(update, make_default=True))


@app.post("/api/settings/instructions/reset")
async def restore_instructions(request: Request):
    return await change_instructions(request, reset_instructions)


async def change_instructions(request: Request, save):
    if not same_origin(request.headers.get("origin"), request.headers.get("host")):
        raise HTTPException(403, "Settings must be saved from Jarvis.")
    # The current bridge retains its snapshot; the browser reconnects on save.
    try:
        save()
    except ValueError:
        raise HTTPException(422, "Invalid local configuration; check data/settings.json.") from None
    except OSError:
        raise HTTPException(500, "Could not save the instructions. Check local file permissions.") from None
    return await get_settings()


@app.websocket("/ws/live")
async def voice(browser: WebSocket):
    if not same_origin(browser.headers.get("origin"), browser.headers.get("host")):
        await browser.close(code=1008)
        return
    await browser.accept()
    if voice_owner.locked():
        await browser.send_json({"type": "error", "code": "busy", "retryable": True,
                                 "message": "Jarvis is already connected in another window."})
        await browser.close(code=1008)
        return
    if not api_key():
        await browser.send_json({"type": "error", "code": "missing_key", "retryable": False,
                                 "message": "Add GEMINI_API_KEY to the local .env file, then restart Jarvis."})
        await browser.close(code=1008)
        return
    try:
        settings = read_settings()
    except ValueError:
        await browser.send_json({"type": "error", "code": "configuration", "retryable": False,
                                 "message": "Invalid local configuration; check data/settings.json."})
        await browser.close(code=1008)
        return
    async with voice_owner:
        await LiveBridge(browser, settings).run()


@app.get("/")
async def index():
    return FileResponse(ROOT / "frontend" / "index.html", headers={"Cache-Control": "no-cache"})


app.mount("/static", StaticFiles(directory=ROOT / "frontend"), name="static")
