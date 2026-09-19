"""
Gemini Live Bidirectional WebSocket Client for J.A.R.V.I.S.
Handles real-time 16kHz audio input, 24kHz response audio, tool calling, and interruptions.
"""

import os
import json
import base64
import asyncio
import time
from datetime import datetime
import websockets
from typing import Optional, Callable, Dict, Any, List
from .prompt_engine import prompt_engine
from .actuator_dispatcher import actuator_dispatcher
from .audio_bridge import audio_bridge
from .memory import memory_engine
from .logger import log_error, log_info, log_warn, log_tool

GEMINI_WS_URL = "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent"
DEFAULT_MODEL = "models/gemini-3.1-flash-live-preview"


SESSION_STATE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "gemini_live_session.json"
)


class GeminiLiveSession:
    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_MODEL, voice_name: str = "Puck"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.model = model
        self.voice_name = voice_name
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.is_connected = False
        self.is_running = False
        self.listeners: List[Callable[[Dict[str, Any]], None]] = []
        self._greeted = False
        self.session_resumption_handle: Optional[str] = self._load_persisted_resumption_handle()
        self._reconnect_lock = asyncio.Lock()
        self._is_reconnecting = False
        self._receiver_task: Optional[asyncio.Task] = None
        self._audio_task: Optional[asyncio.Task] = None

    def _load_persisted_resumption_handle(self) -> Optional[str]:
        """Loads a valid non-expired resumption handle from persistent storage."""
        try:
            if os.path.exists(SESSION_STATE_FILE):
                with open(SESSION_STATE_FILE, "r", encoding="utf-8") as f:
                    st = json.load(f)
                handle = st.get("handle")
                ts = st.get("updated_at", 0)
                # Google Gemini Live resumption handles are valid for up to 2 hours (7200s)
                if handle and (time.time() - ts < 7000):
                    return handle
        except Exception as ex:
            log_warn(f"Could not load persisted session resumption handle: {ex}", source="GeminiLive")
        return None

    def _save_resumption_handle(self, handle: str):
        """Persists the session resumption handle to disk across process restarts."""
        try:
            os.makedirs(os.path.dirname(SESSION_STATE_FILE), exist_ok=True)
            with open(SESSION_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "handle": handle,
                    "updated_at": time.time(),
                    "iso": datetime.now().isoformat()
                }, f, indent=2)
        except Exception as ex:
            log_warn(f"Could not save session resumption handle: {ex}", source="GeminiLive")

    def _clear_resumption_handle(self):
        """Clears expired or invalidated resumption handle."""
        self.session_resumption_handle = None
        try:
            if os.path.exists(SESSION_STATE_FILE):
                os.remove(SESSION_STATE_FILE)
        except Exception:
            pass

    def add_listener(self, listener: Callable[[Dict[str, Any]], None]):
        if listener not in self.listeners:
            self.listeners.append(listener)

    def remove_listener(self, listener: Callable[[Dict[str, Any]], None]):
        if listener in self.listeners:
            self.listeners.remove(listener)

    def _emit(self, event: Dict[str, Any]):
        for cb in self.listeners:
            try:
                cb(event)
            except Exception:
                pass

    async def _teardown_ws(self):
        """Safely tears down active websocket connection and cancels background streaming tasks."""
        self.is_connected = False
        if self._receiver_task and not self._receiver_task.done():
            self._receiver_task.cancel()
            self._receiver_task = None
        if self._audio_task and not self._audio_task.done():
            self._audio_task.cancel()
            self._audio_task = None
        if self.ws:
            try:
                await asyncio.wait_for(self.ws.close(), timeout=2.0)
            except Exception:
                pass
            self.ws = None

    async def connect(self, voice_name: Optional[str] = None, custom_system_instruction: Optional[str] = None):
        self._greeted = False
        if not self.api_key:
            self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

        if not self.api_key:
            log_warn("No GEMINI_API_KEY found. Running in offline/mock mode.", source="GeminiLive")
            return

        if voice_name:
            self.voice_name = voice_name

        if not self.session_resumption_handle:
            self.session_resumption_handle = self._load_persisted_resumption_handle()

        url = f"{GEMINI_WS_URL}?key={self.api_key}"
        resumption_info = f" (resuming continuous handle {self.session_resumption_handle[:16]}...)" if self.session_resumption_handle else " (continuous context enabled)"
        log_info(f"🎙 Connecting to Gemini Live API ({self.model}, voice: {self.voice_name}){resumption_info}...", source="GeminiLive")

        await self._teardown_ws()

        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                self.ws = await websockets.connect(
                    url,
                    max_size=15_000_000,
                    open_timeout=15.0,
                    ping_interval=None,
                    ping_timeout=None,
                    close_timeout=5.0,
                )
                self.is_connected = True
                self.is_running = True

                # Send Setup handshake
                await self._send_setup(custom_system_instruction)

                # Start message receiver task and audio sender task
                self._receiver_task = asyncio.create_task(self._receive_loop())
                self._audio_task = asyncio.create_task(self._audio_sender_loop())
                return

            except Exception as e:
                # If connection or setup failed and we attempted resumption, clear stale handle and retry clean
                if self.session_resumption_handle:
                    log_warn(f"Session resumption failed ({e}). Clearing stale handle and reconnecting cleanly...", source="GeminiLive")
                    self._clear_resumption_handle()

                if attempt < max_retries:
                    log_warn(f"Gemini Live connection attempt {attempt}/{max_retries} failed ({e}). Retrying in 2s...", source="GeminiLive")
                    await asyncio.sleep(2.0)
                else:
                    log_error(f"Connection error after {max_retries} attempts: {e}", source="GeminiLive", exc=e)
                    self.is_connected = False
                    raise

    async def _send_setup(self, custom_system_instruction: Optional[str] = None):
        system_instruction = custom_system_instruction or prompt_engine.render_system_prompt(persona_id="jarvis")
        tools = actuator_dispatcher.get_tool_declarations()

        resumption_cfg = {"handle": self.session_resumption_handle} if self.session_resumption_handle else {}

        setup_msg = {
            "setup": {
                "model": self.model,
                "generationConfig": {
                    "responseModalities": ["AUDIO"],
                    "speechConfig": {
                        "voiceConfig": {
                            "prebuiltVoiceConfig": {
                                "voiceName": self.voice_name
                            }
                        }
                    }
                },
                "systemInstruction": {
                    "parts": [{"text": system_instruction}]
                },
                "tools": [{"functionDeclarations": tools}],
                # Ultra-low latency voice activity detection
                "realtimeInputConfig": {
                    "automaticActivityDetection": {
                        "disabled": False,
                        "startOfSpeechSensitivity": 1,  # HIGH
                        "endOfSpeechSensitivity": 1,    # HIGH
                        "prefixPaddingMs": 40,
                        "silenceDurationMs": 180
                    }
                },
                "inputAudioTranscription": {},
                "outputAudioTranscription": {},
                "sessionResumption": resumption_cfg,
                "contextWindowCompression": {"slidingWindow": {}}
            }
        }
        await self.ws.send(json.dumps(setup_msg))
        print("[GeminiLive] ⚡ Setup handshake sent with Telgish prompt and tool manifests.")

    async def _audio_sender_loop(self):
        """
        Continuously pulls 16kHz PCM audio from AudioBridge and streams to Gemini Live.
        Uses timeout-based queue polling to exit cleanly on disconnect.
        """
        try:
            while self.is_running and self.is_connected:
                try:
                    pcm_chunk = await asyncio.wait_for(audio_bridge.inbound_audio_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                if not pcm_chunk or not self.ws or not self.is_connected:
                    continue

                b64_audio = base64.b64encode(pcm_chunk).decode("utf-8")
                await self.send_realtime_audio(b64_audio)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log_error(f"Audio sender error: {e}", source="GeminiLive", exc=e)

    async def send_realtime_audio(self, b64_audio: str):
        if not self.ws or not self.is_connected:
            return
        msg = {
            "realtimeInput": {
                "audio": {
                    "mimeType": "audio/pcm;rate=16000",
                    "data": b64_audio
                }
            }
        }
        try:
            await self.ws.send(json.dumps(msg))
        except (websockets.exceptions.ConnectionClosed, ConnectionResetError):
            self.is_connected = False
            asyncio.create_task(self.reconnect_with_backoff(initial_delay=1.0))
        except Exception as ex:
            log_warn(f"Audio send error: {ex}", source="GeminiLive")

    async def send_realtime_image(self, b64_image: str, mime_type: str = "image/jpeg"):
        if not self.ws or not self.is_connected:
            return
        msg = {
            "realtimeInput": {
                "video": {
                    "mimeType": mime_type,
                    "data": b64_image
                }
            }
        }
        try:
            await self.ws.send(json.dumps(msg))
        except (websockets.exceptions.ConnectionClosed, ConnectionResetError):
            self.is_connected = False
            asyncio.create_task(self.reconnect_with_backoff(initial_delay=1.0))
        except Exception as ex:
            log_warn(f"Image send error: {ex}", source="GeminiLive")

    async def _receive_loop(self):
        """
        Handles incoming Gemini Live WebSocket frames (audio chunks, tool calls, text turns).
        """
        try:
            async for raw_msg in self.ws:
                data = json.loads(raw_msg)

                if "setupComplete" in data:
                    print("[GeminiLive] 🌟 Gemini Live Bidirectional Session Active & Synchronized.")
                    self._emit({"type": "setup_complete"})
                    asyncio.create_task(self.trigger_greeting())

                if "goAway" in data or "goaway" in data:
                    log_warn("GoAway signal received from Gemini Live. Refreshing session with resumption handle...", source="GeminiLive")
                    await self._teardown_ws()
                    asyncio.create_task(self.reconnect_with_backoff(initial_delay=0.5))
                    return

                # Session resumption handle (2h window)
                if "sessionResumptionUpdate" in data:
                    upd = data["sessionResumptionUpdate"]
                    handle = upd.get("newHandle") or upd.get("handle")
                    if handle:
                        self.session_resumption_handle = handle
                        self._save_resumption_handle(handle)

                # 1. Handle Model Audio Turn & Transcriptions
                server_content = data.get("serverContent")
                if server_content:
                    inp_tr = server_content.get("inputTranscription")
                    if inp_tr and inp_tr.get("text"):
                        txt = inp_tr["text"]
                        self._emit({"type": "input_transcription", "text": txt})
                        memory_engine.log_conversation_turn("User (Gopi)", txt, role="user")
                    out_tr = server_content.get("outputTranscription")
                    if out_tr and out_tr.get("text"):
                        self._emit({"type": "output_transcription", "text": out_tr["text"]})

                    model_turn = server_content.get("modelTurn")
                    if model_turn:
                        for part in model_turn.get("parts", []):
                            inline_data = part.get("inlineData")
                            if inline_data and "audio" in inline_data.get("mimeType", ""):
                                raw_b64 = inline_data["data"]
                                raw_pcm = base64.b64decode(raw_b64)

                                # Forward to React UI WebSocket listeners
                                self._emit({"type": "audio", "audio": raw_b64, "data": raw_b64})

                                # Forward to Rust audio gateway speaker queue (if active)
                                if audio_bridge.client_writer:
                                    await audio_bridge.queue_playback(raw_pcm)

                            if "text" in part:
                                text = part["text"]
                                self._emit({"type": "transcript", "text": text, "role": "agent"})
                                self._emit({"type": "output_transcription", "text": text})
                                memory_engine.log_conversation_turn("JARVIS", text, role="assistant")

                    if server_content.get("interrupted"):
                        print("[GeminiLive] ⚡ Voice output interrupted by operator.")
                        audio_bridge.clear_playback()
                        self._emit({"type": "interrupted"})

                    if server_content.get("turnComplete"):
                        self._emit({"type": "turn_complete"})

                # 2. Handle Tool Calls Concurrently
                tool_call = data.get("toolCall")
                if tool_call:
                    # Spawn tool execution in background task so receive/audio loop NEVER blocks
                    asyncio.create_task(self._process_tool_call_concurrently(tool_call))

        except asyncio.CancelledError:
            pass
        except Exception as e:
            if not self.is_running:
                return
            log_warn(f"Gemini Live connection dropped ({e}). Scheduling resilient reconnect...", source="GeminiLive")
            await self._teardown_ws()
            asyncio.create_task(self.reconnect_with_backoff(initial_delay=1.0))

    async def reconnect_with_backoff(self, initial_delay: float = 1.0, max_retries: int = 15):
        """
        Rock-solid auto-reconnection loop with exponential backoff and single-flight lock.
        Prevents multiple parallel reconnect tasks from trampling each other.
        """
        async with self._reconnect_lock:
            if self.is_connected or not self.is_running:
                return
            if self._is_reconnecting:
                return
            self._is_reconnecting = True

        try:
            self._emit({"type": "session_reconnecting", "status": "reconnecting"})
            delay = initial_delay
            for attempt in range(1, max_retries + 1):
                if not self.is_running or self.is_connected:
                    break

                log_info(f"🔄 Auto-reconnecting Gemini Live (attempt {attempt}/{max_retries}) in {delay:.1f}s...", source="GeminiLive")
                await asyncio.sleep(delay)

                try:
                    await self.connect(voice_name=self.voice_name)
                    if self.is_connected:
                        log_info("🌟 Gemini Live session successfully reconnected and restored!", source="GeminiLive")
                        self._emit({"type": "session_reconnected", "status": "connected"})
                        return
                except Exception as e:
                    log_warn(f"Reconnect attempt {attempt} failed: {e}", source="GeminiLive")

                delay = min(delay * 1.5, 12.0)

            log_error(f"Gemini Live auto-reconnection failed after {max_retries} attempts.", source="GeminiLive")
            self._emit({"type": "session_error", "message": "Voice session lost. Please re-initialize."})
        finally:
            self._is_reconnecting = False

    ASYNC_LONG_RUNNING_TOOLS = {
        "run_full_system_diagnostics",
        "execute_linux_command",
        "forge_custom_tool",
        "test_custom_tool",
        "codebase_search_code",
        "codebase_get_architecture",
        "codebase_trace_path",
        "codebase_detect_changes",
        "codebase_query_graph",
        "delegate_to_prime_agent",
        "delegate_to_ultron",
        "delegate_to_hermes",
        "delegate_task",
    }

    async def _run_background_task(self, call_id: str, name: str, args: Dict[str, Any], task_future: Optional[asyncio.Task] = None):
        start_ms = time.time() * 1000
        is_self_emitting = name in [
            "delegate_to_hermes", "hermes_chat", "delegate_to_ultron",
            "delegate_to_openclaw", "ultron_execute", "start_background_task", "run_background_task"
        ]
        task_id = f"bg_{call_id or int(start_ms)}"
        if not is_self_emitting:
            category = "ultron" if any(k in name for k in ["audit", "boost", "security", "ultron"]) else "system"
            await actuator_dispatcher.emit_task_started(task_id, name.replace("_", " ").title(), category, prompt=str(args))

        try:
            result = await task_future if task_future else await actuator_dispatcher.dispatch_tool(name, args)
        except Exception as ex:
            result = {"success": False, "error": str(ex)}

        duration_ms = (time.time() * 1000) - start_ms
        if not is_self_emitting:
            card = result.get("displayCard")
            await actuator_dispatcher.emit_task_completed(
                task_id,
                result.get("success", False),
                result,
                display_card=card,
                error=result.get("error")
            )

        self._emit({"type": "tool_result", "toolName": name, "result": result})
        memory_engine.log_tool_execution(name, args, result, duration_ms)

        if self.ws and self.is_connected:
            try:
                ok = result.get("success", False)
                detail = result.get("summary") or result.get("message") or result.get("output") or ("Completed successfully." if ok else result.get("error", "Execution failed"))
                status_str = "COMPLETED" if ok else "FAILED"
                directive = (
                    "Proactively speak to your operator Gopi now to report the completion and key outcome in 1 to 2 articulate sentences in your signature Jarvis voice."
                    if ok else
                    "Inform operator Gopi that the background task encountered an error in 1 concise sentence."
                )
                notification = (
                    f"[SYSTEM NOTIFICATION: BACKGROUND TASK {status_str}]\n"
                    f"Task: {name}\n"
                    f"Duration: {duration_ms:.0f}ms\n"
                    f"Outcome: {str(detail)[:300]}\n\n"
                    f"OPERATIONAL DIRECTIVE FOR JARVIS:\n- {directive}"
                )
                await self.send_text_message(notification)
            except Exception as notify_err:
                log_error(f"Failed to notify background task completion: {notify_err}", source="GeminiLive", exc=notify_err)

    async def _process_tool_call_concurrently(self, tool_call: Dict[str, Any]):
        """
        Executes tools in parallel while audio streaming continues uninterrupted.
        Fast tools (< 350ms) return immediate ground truth.
        Long-running tools immediately acknowledge in voice and execute in background,
        allowing Jarvis to listen and speak full-duplex while work proceeds.
        """
        try:
            function_calls = tool_call.get("functionCalls", [])
            if not function_calls:
                return

            async def _execute_single(call: Dict[str, Any]) -> Dict[str, Any]:
                call_id = call.get("id")
                name = call.get("name")
                args = call.get("args", {})
                start_ms = time.time() * 1000
                print(f"[GeminiLive] ⚡ Tool Invoked: {name}({args})")
                self._emit({"type": "tool_call", "name": name, "toolName": name, "args": args})

                # If known long-running tool, dispatch to background immediately (< 5ms)
                if name in self.ASYNC_LONG_RUNNING_TOOLS:
                    asyncio.create_task(self._run_background_task(call_id, name, args))
                    return {
                        "id": call_id,
                        "name": name,
                        "response": {
                            "output": {
                                "status": "in_progress",
                                "message": (
                                    f"Task '{name}' has been initiated and is executing in the background. "
                                    f"Speak an immediate, natural verbal acknowledgment to operator Gopi now "
                                    f"(e.g., 'On it, Boss. Starting {name.replace('_', ' ')} now.', 'Working on that in the background, Sir.') "
                                    f"in 1 concise sentence. Keep listening and stay active to converse with Gopi while the task executes."
                                )
                            }
                        }
                    }

                # Otherwise, attempt fast execution within 350ms
                dispatch_task = asyncio.create_task(actuator_dispatcher.dispatch_tool(name, args))
                try:
                    result = await asyncio.wait_for(asyncio.shield(dispatch_task), timeout=0.35)
                    duration_ms = (time.time() * 1000) - start_ms
                    self._emit({"type": "tool_result", "toolName": name, "result": result})
                    memory_engine.log_tool_execution(name, args, result, duration_ms)
                    return {
                        "id": call_id,
                        "name": name,
                        "response": {"output": result}
                    }
                except asyncio.TimeoutError:
                    # Tool took > 350ms: seamlessly transition to background task
                    print(f"[GeminiLive] ⏳ Tool {name} transitioning to background execution (> 350ms).")
                    asyncio.create_task(self._run_background_task(call_id, name, args, task_future=dispatch_task))
                    return {
                        "id": call_id,
                        "name": name,
                        "response": {
                            "output": {
                                "status": "in_progress",
                                "message": (
                                    f"Task '{name}' has been dispatched to background execution. "
                                    f"Speak a brief acknowledgment to operator Gopi now confirming you are on it, "
                                    f"and remain listening for further input from your operator while the work proceeds."
                                )
                            }
                        }
                    }

            # Run all simultaneous tool calls concurrently in parallel
            responses = await asyncio.gather(*[_execute_single(c) for c in function_calls])

            if self.ws and self.is_connected:
                tool_resp_msg = {
                    "toolResponse": {
                        "functionResponses": list(responses)
                    }
                }
                await self.ws.send(json.dumps(tool_resp_msg))
                log_tool(f"{len(responses)} call(s)", status="response sent")
        except Exception as e:
            log_error(f"Error processing concurrent tool call: {e}", source="GeminiLive", exc=e)

    async def send_text_message(self, text: str):
        if not self.ws or not self.is_connected:
            return

        if not text.startswith("[SYSTEM"):
            memory_engine.log_conversation_turn("User (Gopi)", text, role="user")

        msg = {
            "clientContent": {
                "turns": [
                    {
                        "role": "user",
                        "parts": [{"text": text}]
                    }
                ],
                "turnComplete": True
            }
        }
        try:
            await self.ws.send(json.dumps(msg))
        except (websockets.exceptions.ConnectionClosed, ConnectionResetError):
            self.is_connected = False
            asyncio.create_task(self.reconnect_with_backoff(initial_delay=1.0))
        except Exception as ex:
            log_warn(f"Text send error: {ex}", source="GeminiLive")

    async def trigger_greeting(self, force: bool = False):
        """
        Triggers a natural, time-aware voice greeting from JARVIS to operator Gopi.
        Called on session setup completion or explicit UI activation.
        """
        if not self.ws or not self.is_connected:
            return
        if self._greeted and not force:
            return
        self._greeted = True

        recent_turns = memory_engine.get_recent_conversation_turns(limit=1)
        hour = datetime.now().hour
        time_period = "morning" if 5 <= hour < 12 else "afternoon" if 12 <= hour < 17 else "evening" if 17 <= hour < 22 else "night"
        time_str = datetime.now().strftime("%I:%M %p")

        if recent_turns:
            directive = (
                "- Welcome back your operator Gopi immediately with a spontaneous, natural, crisp 1-sentence greeting "
                "acknowledging system readiness and returning to the session (e.g. 'Welcome back, Sir', 'Online and ready, Gopi', or 'Good evening, Sir. All systems standing by')."
            )
        else:
            directive = (
                "- Greet your operator Gopi immediately with a spontaneous, natural, crisp 1-sentence greeting "
                "acknowledging system readiness."
            )

        dynamic_greeting_prompt = (
            f"[SYSTEM EVENT: VOICE SESSION SYNCHRONIZED]\n"
            f"Current local time: {time_str} ({time_period}).\n"
            f"OPERATIONAL DIRECTIVE:\n"
            f"{directive}\n"
            f"- Pronounce your name naturally as 'Jarvis' (never spell it out letter-by-letter as 'J-A-R-V-I-S').\n"
            f"- Never use a fixed or repetitive cliché template. Reflect the current {time_period} time and system readiness in an alert, self-evolving Jarvis voice."
        )
        log_info(f"🎙 Triggering session greeting (time: {time_str}, period: {time_period}, has_history: {bool(recent_turns)})...", source="GeminiLive")
        await self.send_text_message(dynamic_greeting_prompt)

    async def close(self):
        self.is_running = False
        self.is_connected = False
        await self._teardown_ws()
        print("[GeminiLive] Session closed.")


gemini_session = GeminiLiveSession()
