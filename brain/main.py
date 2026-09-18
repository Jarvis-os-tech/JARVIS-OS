"""
J.A.R.V.I.S. Python Core Engine — Master Entrypoint.
Orchestrates Gemini Live, Unix Socket Audio Bridge, Jinja2 Prompts, and FastAPI.
"""

import os
import sys
import argparse
import asyncio
import signal
import uvicorn
from dotenv import load_dotenv
load_dotenv(os.path.join(os.getcwd(), ".env"))
load_dotenv()

# Add parent directory to path for clean relative imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brain.security import security_guard
from brain.memory import memory_engine
from brain.prompt_engine import prompt_engine
from brain.actuator_dispatcher import actuator_dispatcher
from brain.audio_bridge import audio_bridge, DEFAULT_SOCKET_PATH
from brain.gemini_live import gemini_session
from brain.server import app
from brain.hud import launch_native_hud
from brain.logger import (
    setup_global_logger, print_banner, log_info, log_success,
    log_warn, log_error, log_reminder
)
from brain.reminders import run_reminder_scheduler, reminder_manager


def load_environment():
    load_dotenv(os.path.join(os.getcwd(), ".env"))
    load_dotenv()


async def run_orchestrator(args):
    setup_global_logger()
    tools_count = len(actuator_dispatcher.get_tool_declarations())
    print_banner(persona=args.persona, port=args.port, socket_path=args.socket_path, tools_count=tools_count)

    # 1. Initialize Memory Vault & Fresh Daily Session
    v_status = memory_engine.get_vault_status()
    snapshot = memory_engine.get_frozen_snapshot()
    log_info(f"🧠 Memory Vault Connected: {v_status['vault_root']}", source="Vault")
    log_info(f"📅 Active Daily Conversation: {v_status['today_conversation_file']}", source="Vault")
    log_info(f"📚 Vault Index: {v_status['total_facts_indexed']} facts, {v_status['total_skills_indexed']} skills, {v_status['total_conversations_logged']} conversation logs", source="Vault")

    # 2. Render initial system prompt
    initial_prompt = prompt_engine.render_system_prompt(persona_id=args.persona)
    log_info(f"📜 Initial prompt rendered ({len(initial_prompt)} chars).", source="Prompt")

    # 3. Active Reminders Summary
    active_rems = reminder_manager.list_reminders(include_completed=False)
    if active_rems:
        log_reminder(f"Loaded {len(active_rems)} active scheduled reminder(s).", action="INFO")
    else:
        log_info("⏰ Reminders vault loaded (0 pending).", source="Reminders")

    if args.dry_run:
        log_success("✅ Dry run successful. All subsystems initialized without errors.", source="Core")
        return

    # 4. Start Audio Bridge (Unix Domain Socket server)
    audio_bridge.socket_path = args.socket_path
    await audio_bridge.start()

    # 5. Start Background Reminder Scheduler
    scheduler_task = asyncio.create_task(
        run_reminder_scheduler(
            broadcast_fn=actuator_dispatcher._broadcast_to_ui,
            voice_notify_fn=gemini_session.send_text_message
        )
    )

    log_success("🟢 J.A.R.V.I.S. Core Engine ready. Waiting for UI connection...", source="Core")

    # 6. Start FastAPI server
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=args.port,
        log_level="info",
        access_log=False
    )
    server = uvicorn.Server(config)

    # Automatically open the UI in the default browser unless disabled
    if not getattr(args, "no_browser", False) and not os.environ.get("JARVIS_NO_BROWSER"):
        def open_browser():
            import time
            import webbrowser
            time.sleep(1.0)
            ui_url = f"http://localhost:{args.port}"
            log_info(f"🌐 Launching J.A.R.V.I.S. React UI: {ui_url}", source="Browser")
            try:
                webbrowser.open(ui_url)
            except Exception as b_ex:
                log_warn(f"Could not auto-launch browser: {b_ex}", source="Browser")

        import threading
        threading.Thread(target=open_browser, daemon=True).start()

    try:
        await server.serve()
    finally:
        scheduler_task.cancel()
        await gemini_session.close()
        await audio_bridge.stop()
        log_success("🏁 J.A.R.V.I.S. Python Core Engine shutdown complete.", source="Core")


def main():
    parser = argparse.ArgumentParser(description="JARVIS Python Core Engine")
    parser.add_argument("--port", type=int, default=8000, help="FastAPI port (default: 8000)")
    parser.add_argument("--socket-path", type=str, default=DEFAULT_SOCKET_PATH, help="Unix domain socket path")
    parser.add_argument("--persona", type=str, default="jarvis", help="AI Persona (jarvis, friday, ultron, edith, karen)")
    parser.add_argument("--dry-run", action="store_true", help="Initialize and verify components without listening indefinitely")
    parser.add_argument("--hud", action="store_true", help="Launch native PySide6 desktop HUD overlay")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open UI in browser on launch")
    args = parser.parse_args()

    load_environment()

    if args.hud:
        hud_app = launch_native_hud()

    try:
        asyncio.run(run_orchestrator(args))
    except KeyboardInterrupt:
        print("")
        log_warn("Process interrupted by user.", source="Core")


if __name__ == "__main__":
    main()
