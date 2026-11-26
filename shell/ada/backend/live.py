"""A bounded, full-duplex Gemini connection owned by one browser session."""
from __future__ import annotations

import asyncio
import base64
from contextlib import suppress
import json
import logging
import random
import struct
import time
from typing import Any
from uuid import uuid4

from fastapi import WebSocket, WebSocketDisconnect
from google import genai
from google.genai import types

from .config import Settings, api_key
from .vad import SpeechDetector
from .diagnostics import AudioTrace
from .projects import WorkspaceError, store
from .project_tools import DECLARATIONS, INSTRUCTIONS, READ_ACTIONS, UI_ACTIONS, run_action, validate
from .project_deletion import DELETION_ACTIONS, ProjectDeletion

logger = logging.getLogger("jarvis.live")


class ProjectChanged(Exception):
    """Discard conversational context when the user opens a different project."""


async def send_tool_result(session, response):
    if not response.parts:
        await session.send_tool_response(function_responses=[response])
        return
    # google-genai 2.19.0's Live send_tool_response uses json.dumps on raw
    # bytes. Serialize multimodal responses to the documented wire format
    # here, retaining the same SDK-owned WebSocket and function-call ID.
    payload = response.model_dump(mode='json', by_alias=True, exclude_none=True)
    for part, encoded in zip(response.parts, payload['parts']):
        if part.inline_data:
            encoded['inlineData']['data'] = base64.b64encode(part.inline_data.data).decode('ascii')
    await session._ws.send(json.dumps({'toolResponse': {'functionResponses': [payload]}}))


def retry_delay(failures: int) -> float:
    """Bound both exponential backoff and jitter, including persistent outages."""
    return min(10., .5 * 2 ** min(max(0, failures), 5) * random.uniform(.8, 1.2))


def live_config(settings: Settings, handle: str | None = None, context: str = '') -> dict:
    return {
        "response_modalities": ["AUDIO"],
        "system_instruction": settings.instructions + '\n' + INSTRUCTIONS + '\nPROJECT REFERENCE DATA:\n' + context,
        "tools": [{"function_declarations": DECLARATIONS}],
        "speech_config": {"voice_config": {"prebuilt_voice_config": {"voice_name": settings.voice}}},
        "input_audio_transcription": {},
        "output_audio_transcription": {},
        "realtime_input_config": {
            "activity_handling": "START_OF_ACTIVITY_INTERRUPTS",
            "automatic_activity_detection": {
                "disabled": False,
                "start_of_speech_sensitivity": "START_SENSITIVITY_HIGH" if settings.sensitivity == "sensitive" else "START_SENSITIVITY_LOW",
                "end_of_speech_sensitivity": "END_SENSITIVITY_LOW",
                "prefix_padding_ms": settings.prefix_ms,
                "silence_duration_ms": settings.silence_ms,
            },
        },
        "session_resumption": {"handle": handle},
        "context_window_compression": {"sliding_window": {}},
    }


class TurnStream:
    """Translate every content part while keeping cancellation and turn IDs ordered."""

    def __init__(self, epoch: int) -> None:
        self.epoch = epoch
        self.turn = 0
        self.active = False
        self.discard = False
        self.stopped_turn = -1

    def stop(self) -> None:
        self.stopped_turn = self.turn

    def process(self, content: Any) -> list[dict | bytes]:
        events: list[dict | bytes] = []
        incoming = getattr(content, "input_transcription", None)
        if incoming and incoming.text:
            events.append({"type": "transcript", "role": "user", "text": incoming.text,
                           "finished": bool(getattr(incoming, "finished", False)), "epoch": self.epoch})
        interrupted = bool(content.interrupted)
        if interrupted:
            self.discard = True
            events.append({"type": "interrupted", "epoch": self.epoch, "turn": self.turn})

        if not self.discard:
            output = getattr(content, "output_transcription", None)
            parts = getattr(getattr(content, "model_turn", None), "parts", None) or []
            has_output = bool(output and output.text) or any(getattr(p, "inline_data", None) for p in parts)
            if has_output and not self.active:
                self.turn += 1
                self.active = True
                events.append({"type": "turn_started", "epoch": self.epoch, "turn": self.turn})
            if self.turn != self.stopped_turn:
                if output and output.text:
                    events.append({"type": "transcript", "role": "assistant", "text": output.text,
                                   "epoch": self.epoch, "turn": self.turn})
                for part in parts:
                    blob = getattr(part, "inline_data", None)
                    if blob and blob.data and (blob.mime_type or "").startswith("audio/pcm"):
                        # An explicit header lets the player reject obsolete sessions/turns.
                        events.append(struct.pack("<III", self.epoch, self.turn, 24000) + blob.data)
        if getattr(content, "generation_complete", False) and not self.discard:
            events.append({"type": "generation_complete", "epoch": self.epoch, "turn": self.turn})
        if content.turn_complete:
            events.append({"type": "turn_complete", "epoch": self.epoch, "turn": self.turn})
            self.active = False
            self.discard = False
        if getattr(content, "waiting_for_input", False):
            events.append({"type": "waiting", "epoch": self.epoch})
        return events


class LiveBridge:
    def __init__(self, browser: WebSocket, settings: Settings) -> None:
        self.browser = browser
        self.settings = settings
        self.send_lock = asyncio.Lock()
        self.audio: asyncio.Queue[bytes] = asyncio.Queue(maxsize=15)
        self.control: asyncio.Queue[dict] = asyncio.Queue(maxsize=16)
        self.ready = False
        self.muted = False
        self.epoch = 0
        self.turns = TurnStream(0)
        self.vad = SpeechDetector(settings.silence_ms)
        self.dropped = 0
        self.closed = False
        self.trace = AudioTrace()
        self.project_id = store.active()
        self.tool_queue = asyncio.Queue(maxsize=32)
        self.cancelled_tools = set()
        self.tool_results = {}
        self.latest_request = ''
        self.user_transcript = ''
        self.project_handoff = None
        self.ui_requests = {}
        self.user_sequence = 0
        self.project_deletion = ProjectDeletion()

    async def send(self, event: dict | bytes) -> None:
        async with self.send_lock:
            if isinstance(event, bytes):
                await asyncio.wait_for(self.browser.send_bytes(event), timeout=3)
            else:
                await asyncio.wait_for(self.browser.send_json(event), timeout=3)
            self.trace.observe(event)

    def clear_audio(self) -> None:
        while not self.audio.empty():
            self.audio.get_nowait()
        self.vad.reset()

    async def receive_browser(self) -> None:
        while True:
            message = await self.browser.receive()
            if message["type"] == "websocket.disconnect":
                self.closed = True
                return
            data = message.get("bytes")
            if data is not None:
                if len(data) != SpeechDetector.FRAME_BYTES:
                    await self.send({"type": "error", "code": "audio_format", "retryable": False,
                                     "message": "Invalid microphone audio frame."})
                    self.closed = True
                    return
                if not self.ready or self.muted:
                    continue
                self.trace.received += 1
                for event in self.vad.feed(data):
                    await self.send(event)
                self.trace.peak_rms = max(self.trace.peak_rms, self.vad.rms)
                if self.audio.full():
                    self.audio.get_nowait()
                    self.dropped += 1
                self.audio.put_nowait(data)
            elif message.get("text"):
                import json
                try:
                    command = json.loads(message["text"])
                except ValueError:
                    continue
                if not isinstance(command, dict):
                    continue
                kind = command.get("type")
                if kind == 'ui_result':
                    request_id = command.get('id')
                    future = self.ui_requests.get(request_id) if isinstance(request_id, str) else None
                    if future and not future.done():
                        if command.get('ok') is True and isinstance(command.get('result'), dict):
                            future.set_result(command['result'])
                        else:
                            future.set_exception(WorkspaceError(str(command.get('error', 'Screen action failed.'))[:500]))
                elif kind == "stop":
                    self.turns.stop()
                    await self.send({"type": "interrupted", "epoch": self.epoch, "turn": self.turns.turn})
                elif kind == "mute":
                    self.muted = bool(command.get("muted"))
                    self.trace.log("microphone_mute", muted=self.muted)
                    self.clear_audio()
                    if self.ready and self.muted and not self.control.full():
                        self.control.put_nowait({"type": "stream_end"})
                    await self.send({"type": "speech", "active": False})
                elif kind == "text" and self.ready and isinstance(command.get("text"), str):
                    text = command["text"].strip()[:4000]
                    if text and not self.control.full():
                        self.user_sequence += 1
                        self.user_transcript = ''
                        self.latest_request = text
                        # Text explicitly starts a new turn and cancels current playback.
                        self.turns.stop()
                        await self.send({"type": "interrupted", "epoch": self.epoch, "turn": self.turns.turn})
                        self.control.put_nowait({"type": "text", "text": text})

    async def send_gemini(self, session: Any) -> None:
        while True:
            if not self.control.empty():
                control = self.control.get_nowait()
                if control["type"] == "stream_end":
                    await asyncio.wait_for(session.send_realtime_input(audio_stream_end=True), 5)
                else:
                    await asyncio.wait_for(session.send_client_content(
                        turns=types.Content(role="user", parts=[types.Part(text=control["text"])]),
                        turn_complete=control.get('type') != 'context'), 5)
                continue
            try:
                data = await asyncio.wait_for(self.audio.get(), timeout=0.04)
            except TimeoutError:
                continue
            if not self.muted:
                await asyncio.wait_for(session.send_realtime_input(
                    audio=types.Blob(data=data, mime_type="audio/pcm;rate=16000")), 5)
                self.trace.sent += 1

    async def receive_gemini(self, session: Any, state: dict) -> None:
        while True:
            async for message in session.receive():
                self.trace.last_gemini = time.monotonic()
                update = message.session_resumption_update
                if update and update.resumable and update.new_handle:
                    state["handle"] = update.new_handle
                if message.go_away:
                    state["go_away"] = True
                    return
                cancellation = getattr(message, 'tool_call_cancellation', None)
                if cancellation:
                    self.cancelled_tools.update(cancellation.ids or [])
                calls = getattr(message, 'tool_call', None)
                if calls:
                    for call in calls.function_calls or []:
                        await self.tool_queue.put(call)
                content = message.server_content
                if content:
                    for event in self.turns.process(content):
                        if isinstance(event, dict) and event.get('type') == 'transcript' and event.get('role') == 'user':
                            if not self.user_transcript:
                                self.user_sequence += 1
                            self.user_transcript = (self.user_transcript + event['text'])[-4000:]
                            self.latest_request = self.user_transcript
                        elif isinstance(event, dict) and event.get('type') == 'turn_started':
                            self.user_transcript = ''
                        pending = self.project_deletion.pending
                        if pending and pending['sequence'] == self.user_sequence and isinstance(event, dict):
                            if event.get('type') == 'transcript' and event.get('role') == 'assistant':
                                pending['spoken'] = True
                            if event.get('type') == 'turn_complete' and pending.get('spoken'):
                                pending['asked'] = True
                        await self.send(event)

    async def execute_tools(self, session, project_id):
        """Keep disk/PDF work off the voice receive loop; never retry a committed call."""
        while True:
            call = await self.tool_queue.get()
            if call.id in self.cancelled_tools:
                continue
            key = (call.id, call.name)
            request = self.latest_request
            response_parts = None
            result = self.tool_results.get(key) if call.id and call.name != 'inspect_image' else None
            if result is None:
                await self.send({'type': 'tool_status', 'name': call.name, 'status': 'working'})
                try:
                    arguments = dict(call.args or {})
                    if call.name in {'inventory_change', 'scan_inventory', 'refine_inventory_scan', 'generate_cad'} and call.id:
                        arguments['request_id'] = 'voice:' + call.id
                    if call.name in DELETION_ACTIONS:
                        validate(call.name, arguments)
                        operation = asyncio.create_task(asyncio.to_thread(
                            self.project_deletion.run, call.name, arguments, sequence=self.user_sequence,
                            request=request, context_id=project_id))
                    elif call.name in UI_ACTIONS:
                        validate(call.name, arguments)
                        if store.active() != project_id:
                            raise WorkspaceError('The active project changed. Please retry in the current conversation.')
                        result = await self.request_ui(call.name, arguments)
                        operation = None
                    else:
                        operation = asyncio.create_task(asyncio.to_thread(
                            run_action, call.name, arguments, context_id=project_id, from_voice=True))
                    try:
                        if operation is not None:
                            result = await asyncio.shield(operation)
                    except asyncio.CancelledError:
                        # A disk transaction already in progress must finish and be remembered,
                        # even if transport recovery cancels this worker before it can reply.
                        try:
                            committed = await operation
                            self.remember_project_handoff(call.name, committed, project_id, request)
                            if call.id and call.name != 'inspect_image':
                                self.tool_results[key] = {'ok': True, 'result': committed}
                        except (WorkspaceError, OSError, ValueError, KeyError, TypeError):
                            pass
                        raise
                    if call.name == 'inspect_image':
                        response_parts = [types.FunctionResponsePart(inline_data=types.FunctionResponseBlob(
                            data=result.pop('image'), mime_type='image/jpeg', display_name='project-image.jpg'))]
                        result['image'] = {'$ref': 'project-image.jpg'}
                    self.remember_project_handoff(call.name, result, project_id, request)
                    result = {'ok': True, 'result': result}
                except WorkspaceError as error:
                    result = {'ok': False, 'error': str(error)}
                except TimeoutError:
                    result = {'ok': False, 'error': 'The screen did not confirm this action. Check the current view before retrying.'}
                except (OSError, ValueError, KeyError, TypeError):
                    result = {'ok': False, 'error': 'Could not complete the workspace action. Check its arguments and local storage.'}
                if call.id and call.name != 'inspect_image':
                    self.tool_results[key] = result
                    if len(self.tool_results) > 256:
                        self.tool_results.pop(next(iter(self.tool_results)))
                if call.name not in READ_ACTIONS | UI_ACTIONS and result['ok']:
                    await self.send({'type': 'workspace_changed'})
                await self.send({'type': 'tool_status', 'name': call.name, 'status': 'done' if result['ok'] else 'error',
                                 'message': result.get('error', '')})
            if result['ok'] and store.active() != project_id:
                # Do not wake the old conversation with a successful switch result.
                # It could speak or issue more tools before the polling watcher runs,
                # then repeat that work when the fresh conversation continues it.
                self.ready = False
                raise ProjectChanged()
            if call.id not in self.cancelled_tools:
                # Keep the result in model context without starting another spoken turn.
                # SILENT scheduling is supported by this tool's NON_BLOCKING declaration.
                scheduling = ('SILENT' if result['ok'] else 'WHEN_IDLE') if call.name == 'generate_demo_image' else None
                await send_tool_result(session, types.FunctionResponse(
                    id=call.id, name=call.name, response=result, parts=response_parts, scheduling=scheduling))

    def remember_project_handoff(self, name, result, project_id, request):
        if name == 'confirm_project_deletion' and result.get('deleted') and store.active() != project_id:
            self.project_handoff = {'project_id': store.active(), 'request': '',
                                    'completed': f'The user confirmed deletion of {result["name"]!r}. '
                                    'The deletion succeeded. Briefly confirm that it was removed from the library, '
                                    'then wait for the user. Do not create or open any project.'}
        if name in {'create_project', 'open_project'}:
            destination = result.get('id') if name == 'create_project' else result.get('project', {}).get('id')
            if destination and destination != project_id and store.active() == destination:
                self.project_handoff = {'project_id': destination, 'request': request}

    async def request_ui(self, name, arguments):
        request_id = uuid4().hex
        future = asyncio.get_running_loop().create_future()
        self.ui_requests[request_id] = future
        try:
            await self.send({'type': 'ui_request', 'id': request_id, 'name': name, 'arguments': arguments,
                             'project_id': self.project_id, 'epoch': self.epoch})
            return await asyncio.wait_for(future, 12)
        finally:
            self.ui_requests.pop(request_id, None)
            if not future.done(): future.cancel()

    async def watch_project(self, project_id):
        while True:
            try:
                await asyncio.wait_for(asyncio.Event().wait(), .5)
            except TimeoutError:
                pass
            active = store.active()
            if active != project_id:
                raise ProjectChanged()

    async def connection_loop(self) -> None:
        client = genai.Client(api_key=api_key())
        state: dict[str, Any] = {"handle": None}
        failures = 0
        try:
            while not self.closed:
                active = store.active()
                if active != self.project_id:
                    self.project_deletion.pending = None
                    state['handle'] = None
                    self.project_id = active
                    self.user_transcript = ''
                    self.tool_results.clear()
                    self.cancelled_tools.clear()
                self.ready = False
                self.clear_audio()
                while not self.control.empty():
                    self.control.get_nowait()
                self.epoch += 1
                if not state['handle'] and self.epoch > 1:
                    self.tool_results.clear()
                    self.cancelled_tools.clear()
                self.turns = TurnStream(self.epoch)
                while not self.tool_queue.empty():
                    self.tool_queue.get_nowait()
                await self.send({"type": "connecting", "epoch": self.epoch, "resuming": bool(state["handle"])})
                connected_at = None
                state["go_away"] = False
                try:
                    context = await asyncio.to_thread(store.context)
                    config = live_config(self.settings, state["handle"], context)
                    async with client.aio.live.connect(model=self.settings.model, config=config) as session:
                        self.clear_audio()
                        self.ready = True
                        connected_at = asyncio.get_running_loop().time()
                        await self.send({"type": "ready", "epoch": self.epoch, "model": self.settings.model,
                                         "debug": self.trace.enabled})
                        if self.project_handoff and self.project_handoff['project_id'] == self.project_id:
                            request = self.project_handoff['request']
                            completed = self.project_handoff.get('completed')
                            self.project_handoff = None
                            self.control.put_nowait({'type': 'text', 'text': completed or
                                'The requested project has already been created/opened successfully. Do not repeat that action. '
                                'Continue this current user request in the active project, following the project drafting workflow '
                                'when applicable. Inspect the saved content first and complete only missing work; do not restart '
                                'setup or repeat earlier announcements. Finish saving the requested content, give one brief '
                                'summary, then wait for the user: ' + request})
                        tasks = [asyncio.create_task(self.send_gemini(session)),
                                 asyncio.create_task(self.receive_gemini(session, state)),
                                 asyncio.create_task(self.execute_tools(session, self.project_id)),
                                 asyncio.create_task(self.watch_project(self.project_id))]
                        try:
                            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                            for task in done:
                                task.result()
                        finally:
                            for task in tasks:
                                task.cancel()
                            await asyncio.gather(*tasks, return_exceptions=True)
                except ProjectChanged:
                    state['handle'] = None
                    continue
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    # Never put SDK exception text (which can contain URLs/keys) in the UI/log.
                    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
                    safe_code = str(code) if str(code).isdigit() else "unknown"
                    logger.warning("Live connection failed: %s, code=%s", type(exc).__name__, safe_code)
                    fatal = safe_code in {"400", "401", "403", "404", "1007", "1008"}
                    if state["handle"] and str(code) == "400":
                        state["handle"] = None
                        fatal = False
                    if fatal:
                        reason = "authentication" if safe_code in {"401", "403"} else "model_configuration"
                        await self.send({"type": "error", "code": reason, "retryable": False, "message":
                            "Gemini rejected the connection. Check the API key in .env and your model configuration."})
                        return
                finally:
                    self.ready = False
                    self.clear_audio()
                if self.closed:
                    return
                # Brief successful handshakes do not reset an outage's backoff.
                stable = connected_at is not None and asyncio.get_running_loop().time() - connected_at >= 20
                failures = 0 if stable or state["go_away"] else min(failures + 1, 6)
                delay = retry_delay(failures)
                await self.send({"type": "reconnecting", "epoch": self.epoch, "retry_after": delay})
                await asyncio.sleep(delay)
        finally:
            with suppress(Exception):
                await asyncio.wait_for(client.aio.aclose(), 3)

    async def trace_transport(self) -> None:
        while not self.closed:
            await asyncio.sleep(10)
            self.trace.snapshot(ready=self.ready, muted=self.muted, queued=self.audio.qsize(), dropped=self.dropped)

    async def run(self) -> None:
        self.trace.log("session_open", model=self.settings.model, voice=self.settings.voice,
                       sensitivity=self.settings.sensitivity, silence_ms=self.settings.silence_ms,
                       echo_cancellation=self.settings.echo_cancellation)
        tasks = [asyncio.create_task(self.receive_browser()), asyncio.create_task(self.connection_loop())]
        if self.trace.enabled:
            tasks.append(asyncio.create_task(self.trace_transport()))
        try:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        except (WebSocketDisconnect, RuntimeError, TimeoutError):
            pass
        finally:
            self.closed = True
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            self.trace.snapshot(ready=self.ready, muted=self.muted, queued=self.audio.qsize(), dropped=self.dropped)
            self.trace.log("session_closed")
            with suppress(Exception):
                await self.browser.close()
