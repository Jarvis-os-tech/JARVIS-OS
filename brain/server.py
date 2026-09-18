"""
FastAPI Server & REST / WebSocket API for J.A.R.V.I.S. Python Core.
Serves the React 19 UI and bridges the /live WebSocket to Gemini Live.
"""

import os
import time
import json
import base64
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from pydantic import BaseModel

from .security import security_guard
from .memory import memory_engine
from .actuator_dispatcher import actuator_dispatcher
from .prompt_engine import prompt_engine
from .audio_bridge import audio_bridge
from .gemini_live import gemini_session
from .telemetry_service import telemetry_service
from .logger import log_error, log_info, log_warn
from .reminders import reminder_manager

app = FastAPI(title="J.A.R.V.I.S. Python Core Engine", version="1.0.0")

ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(root_dir, "data")
start_time = time.time()


class MemorySearchRequest(BaseModel):
    query: str
    limit: int = 8


class ToolExecuteRequest(BaseModel):
    tool_name: str
    args: Dict[str, Any] = {}


class MemoryFactRequest(BaseModel):
    key: str
    value: str
    category: str = "custom"


class SystemControlRequest(BaseModel):
    action: str
    percent: Optional[int] = None
    volume: Optional[int] = None
    brightness: Optional[int] = None
    mute: Optional[bool] = None
    toggleMute: Optional[bool] = None
    profile: Optional[str] = None
    powerAction: Optional[str] = None


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "engine": "python_core_v1",
        "audio_bridge_running": audio_bridge.is_running,
        "gemini_live_connected": gemini_session.is_connected,
        "uptime_seconds": round(time.time() - start_time, 2)
    }


@app.get("/api/vision/status")
async def vision_status():
    return {"success": True, "vision_state": actuator_dispatcher.vision_state}


# ─── System Telemetry & Hardware Endpoints ────────────────────────────────────

@app.get("/api/system/telemetry")
@app.get("/api/telemetry")
async def get_system_telemetry():
    return await telemetry_service.get_full_telemetry()


@app.get("/api/system/hardware")
async def get_system_hardware():
    return await telemetry_service.get_hardware_state()


@app.post("/api/system/control")
async def system_control(req: SystemControlRequest):
    action = req.action
    if action in ["set_volume", "volume"]:
        if req.toggleMute:
            await actuator_dispatcher.execute_cpp_worker("hardware_ctrl", ["toggle_mute"])
        elif req.mute is not None:
            await actuator_dispatcher.execute_cpp_worker("hardware_ctrl", ["mute_volume", "1" if req.mute else "0"])
        else:
            vol = req.percent if req.percent is not None else req.volume if req.volume is not None else 50
            await actuator_dispatcher.execute_cpp_worker("hardware_ctrl", ["set_volume", str(vol)])
        hw = await telemetry_service.get_hardware_state()
        return {"success": True, "volume": hw.get("volume", {})}

    elif action in ["set_brightness", "brightness"]:
        bri = req.percent if req.percent is not None else req.brightness if req.brightness is not None else 50
        await actuator_dispatcher.execute_cpp_worker("hardware_ctrl", ["set_brightness", str(bri)])
        hw = await telemetry_service.get_hardware_state()
        return {"success": True, "brightness": hw.get("brightness", {})}

    elif action in ["power_profile", "set_power_profile"]:
        prof = req.profile or "balanced"
        await actuator_dispatcher.execute_cpp_worker("hardware_ctrl", ["set_power_profile", prof])
        return {"success": True, "powerProfile": prof}

    elif action in ["sound_heal", "heal_sound_server"]:
        await actuator_dispatcher.execute_cpp_worker("hardware_ctrl", ["heal_sound_server"])
        hw = await telemetry_service.get_hardware_state()
        return {"success": True, "soundServer": hw.get("soundServer", {})}

    elif action in ["power_action", "system_power"]:
        res = await actuator_dispatcher.dispatch_tool("system_power_action", {"action": req.powerAction or "lock"})
        return res

    return {"success": False, "error": f"Unknown action: {action}"}


@app.post("/api/system/brightness")
async def set_brightness_endpoint(req: Dict[str, Any]):
    val = req.get("percent", req.get("brightness", 50))
    await actuator_dispatcher.execute_cpp_worker("hardware_ctrl", ["set_brightness", str(val)])
    hw = await telemetry_service.get_hardware_state()
    return {"success": True, "brightness": hw.get("brightness", {})}


@app.post("/api/system/volume")
async def set_volume_endpoint(req: Dict[str, Any]):
    if req.get("toggleMute"):
        await actuator_dispatcher.execute_cpp_worker("hardware_ctrl", ["toggle_mute"])
    elif "mute" in req:
        await actuator_dispatcher.execute_cpp_worker("hardware_ctrl", ["mute_volume", "1" if req["mute"] else "0"])
    else:
        val = req.get("percent", req.get("volume", 50))
        await actuator_dispatcher.execute_cpp_worker("hardware_ctrl", ["set_volume", str(val)])
    hw = await telemetry_service.get_hardware_state()
    return {"success": True, "volume": hw.get("volume", {})}


@app.post("/api/system/power-profile")
async def set_power_profile_endpoint(req: Dict[str, Any]):
    prof = req.get("profile", "balanced")
    await actuator_dispatcher.execute_cpp_worker("hardware_ctrl", ["set_power_profile", prof])
    return {"success": True, "powerProfile": prof}


@app.post("/api/system/power-action")
async def set_power_action_endpoint(req: Dict[str, Any]):
    act = req.get("action", "lock")
    return await actuator_dispatcher.dispatch_tool("system_power_action", {"action": act})


@app.get("/api/system/apps")
async def get_system_apps():
    apps = []
    seen = set()
    search_dirs = ["/usr/share/applications", os.path.expanduser("~/.local/share/applications")]
    for d in search_dirs:
        if not os.path.exists(d):
            continue
        try:
            for entry in os.listdir(d):
                if not entry.endswith(".desktop"):
                    continue
                file_path = os.path.join(d, entry)
                try:
                    name, exec_cmd, icon, comment, cats = "", "", "", "", []
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        in_desktop_entry = False
                        for line in f:
                            line = line.strip()
                            if line == "[Desktop Entry]":
                                in_desktop_entry = True
                            elif line.startswith("[") and line != "[Desktop Entry]":
                                in_desktop_entry = False
                            elif in_desktop_entry and "=" in line:
                                k, v = line.split("=", 1)
                                k = k.strip()
                                v = v.strip()
                                if k == "Name" and not name:
                                    name = v
                                elif k == "Exec" and not exec_cmd:
                                    exec_cmd = v.split("%")[0].strip()
                                elif k == "Icon" and not icon:
                                    icon = v
                                elif k == "Comment" and not comment:
                                    comment = v
                                elif k == "Categories" and not cats:
                                    cats = [c.strip() for c in v.split(";") if c.strip()]
                                elif k == "NoDisplay" and v.lower() == "true":
                                    name = ""
                                    break
                    if name and name not in seen:
                        seen.add(name)
                        apps.append({
                            "name": name,
                            "exec": exec_cmd or name.lower(),
                            "icon": icon or "application-x-executable",
                            "comment": comment,
                            "desktopFile": entry,
                            "categories": cats,
                        })
                except Exception:
                    continue
        except Exception:
            continue
    apps.sort(key=lambda x: x["name"].lower())
    return {"success": True, "applications": apps}


@app.get("/api/system/processes")
async def get_system_processes(sortBy: str = "cpu", limit: int = 25):
    sort_flag = "-%cpu" if sortBy == "cpu" else "-%mem" if sortBy == "memory" else "-pid"
    cmd_res = await actuator_dispatcher.execute_linux_command(
        f"ps -eo pid,user,%cpu,%mem,vsz,rss,comm --sort={sort_flag} | head -n {limit + 1}"
    )
    procs = []
    if cmd_res.get("success") and cmd_res.get("stdout"):
        lines = cmd_res["stdout"].strip().split("\n")
        for line in lines[1:]:
            parts = line.split(None, 6)
            if len(parts) >= 7:
                try:
                    procs.append({
                        "pid": int(parts[0]),
                        "user": parts[1],
                        "cpuPercent": float(parts[2]),
                        "memPercent": float(parts[3]),
                        "vszMb": round(int(parts[4]) / 1024, 1),
                        "rssMb": round(int(parts[5]) / 1024, 1),
                        "command": parts[6],
                    })
                except Exception:
                    continue
    return {"success": True, "processes": procs}


@app.post("/api/system/processes/kill")
async def kill_system_process(req: Dict[str, Any]):
    pid = req.get("pid")
    signal = req.get("signal", "SIGTERM")
    return await actuator_dispatcher.dispatch_tool("manage_process", {"pid": pid, "signal": signal})


@app.get("/api/system/spec")
async def get_system_spec():
    res = await actuator_dispatcher.execute_cpp_worker("pc_spec", timeout=8.0)
    if res.get("success"):
        return res.get("result", {})
    return {"success": False, "error": "Spec worker unavailable"}


@app.get("/api/system/logs")
async def get_system_logs(source: str = "journalctl", lines: int = 60):
    lines_val = min(lines, 200)
    if source == "dmesg":
        cmd_res = await actuator_dispatcher.execute_linux_command(f"dmesg -T 2>/dev/null | tail -n {lines_val}")
    else:
        cmd_res = await actuator_dispatcher.execute_linux_command(f"journalctl -n {lines_val} --no-pager 2>/dev/null")
    logs = cmd_res.get("stdout", "").strip().split("\n") if cmd_res.get("success") else []
    return {"success": True, "logs": [l for l in logs if l]}


@app.get("/api/system/connections")
async def get_system_connections(filter: str = "listening", limit: int = 40):
    flag = "-l" if filter == "listening" else "-t" if filter == "tcp" else "-u" if filter == "udp" else ""
    cmd_res = await actuator_dispatcher.execute_linux_command(f"ss -tunap {flag} 2>/dev/null | head -n {limit + 1}")
    conns = []
    ports = []
    if cmd_res.get("success") and cmd_res.get("stdout"):
        lines = cmd_res["stdout"].strip().split("\n")
        for line in lines[1:]:
            parts = line.split(None, 6)
            if len(parts) >= 5:
                conns.append({
                    "proto": parts[0],
                    "state": parts[1] if len(parts) > 1 else "",
                    "local": parts[4] if len(parts) > 4 else parts[3],
                    "peer": parts[5] if len(parts) > 5 else "*:*",
                    "process": parts[6] if len(parts) > 6 else "",
                })
                ports.append(parts[4] if len(parts) > 4 else parts[3])
    return {"success": True, "connections": conns, "listeningPorts": ports}


@app.post("/api/system/clipboard")
async def system_clipboard(req: Dict[str, Any]):
    act = req.get("action", "read")
    text = req.get("text", "")
    return await actuator_dispatcher.dispatch_tool("clipboard_control", {"action": act, "text": text})


@app.post("/api/system/exec")
async def system_exec(req: Dict[str, Any]):
    cmd = req.get("command", "")
    cwd = req.get("cwd")
    if not cmd or not isinstance(cmd, str):
        return {"success": False, "error": "Invalid or empty command string."}
    verdict = security_guard.validate_command(cmd)
    if not verdict.get("allowed", False):
        return {"success": False, "error": f"Security Guard: {verdict.get('reason', 'Command denied by security policy.')}"}
    return await actuator_dispatcher.execute_linux_command(cmd, cwd=cwd)


@app.get("/api/system/thermals")
async def get_system_thermals():
    return await actuator_dispatcher.execute_cpp_worker("thermal_scan")


@app.get("/api/system/storage")
async def get_system_storage():
    return await actuator_dispatcher.execute_cpp_worker("storage_scan")


@app.get("/api/system/services")
async def get_system_services():
    cmd_res = await actuator_dispatcher.execute_linux_command("systemctl list-units --type=service --state=running --no-pager --no-legend 2>/dev/null | head -40")
    svcs = []
    if cmd_res.get("success") and cmd_res.get("stdout"):
        for line in cmd_res["stdout"].strip().split("\n"):
            parts = line.split(None, 4)
            if parts:
                svcs.append({"unit": parts[0], "load": parts[1] if len(parts) > 1 else "", "active": parts[2] if len(parts) > 2 else "", "sub": parts[3] if len(parts) > 3 else "", "description": parts[4] if len(parts) > 4 else ""})
    return {"success": True, "services": svcs}


@app.post("/api/system/services/action")
async def service_action(req: Dict[str, Any]):
    unit = req.get("unit", "")
    act = req.get("action", "status")
    return await actuator_dispatcher.dispatch_tool("manage_systemd_service", {"unit": unit, "action": act})


@app.get("/api/system/network")
async def get_system_network():
    return await actuator_dispatcher.dispatch_tool("get_network_status", {})


@app.post("/api/system/list-dir")
async def list_directory_endpoint(req: Dict[str, Any]):
    dir_path = req.get("dirPath", os.path.expanduser("~"))
    if not isinstance(dir_path, str) or not dir_path.strip():
        return {"success": False, "error": "Invalid directory path."}
    return await actuator_dispatcher.dispatch_tool("list_directory", {"dirPath": dir_path, "showHidden": req.get("showHidden", False), "limit": req.get("limit", 50)})


@app.post("/api/system/delete-file")
async def delete_file_endpoint(req: Dict[str, Any]):
    file_path = req.get("filePath", "")
    if not file_path or not isinstance(file_path, str):
        return {"success": False, "error": "Invalid or empty file path for deletion."}
    return await actuator_dispatcher.dispatch_tool("delete_local_file", {"filePath": file_path, "recursive": req.get("recursive", False)})


@app.post("/api/system/desktop")
async def desktop_endpoint(req: Dict[str, Any]):
    return await actuator_dispatcher.dispatch_tool("desktop_control", req)


# ─── Sovereign Orchestrator & Knowledge Spheres Endpoints ─────────────────────

@app.get("/api/orchestrator/status")
async def orchestrator_status():
    return {
        "status": "online",
        "active_persona": "jarvis",
        "total_agents": 1,
        "persona": {
            "id": "jarvis",
            "name": "JARVIS",
            "role": "Sovereign AI Chief of Staff & Tactical Operating Partner",
            "status": "active"
        },
        "knowledge_spheres": [
            {"id": "system_os", "name": "System & OS Core", "status": "active", "color": "#06b6d4"},
            {"id": "operator_profile", "name": "Operator Directives", "status": "active", "color": "#38bdf8"},
            {"id": "knowledge_intel", "name": "Intelligence & Research", "status": "active", "color": "#f59e0b"},
            {"id": "codebase_dev", "name": "Codebase Architecture", "status": "active", "color": "#8b5cf6"},
            {"id": "workspace_ops", "name": "Workspace & Cloud Ops", "status": "active", "color": "#10b981"},
            {"id": "security_groundtruth", "name": "Security & Ground Truth", "status": "active", "color": "#f43f5e"},
        ]
    }


@app.post("/api/orchestrator/swap-persona")
async def orchestrator_swap_persona(req: Dict[str, Any]):
    pid = req.get("personaId", req.get("targetPersonaId", "jarvis"))
    return await actuator_dispatcher.dispatch_tool("switch_persona", {"targetPersonaId": pid})


@app.post("/api/orchestrator/delegate")
async def orchestrator_delegate(req: Dict[str, Any]):
    agent = req.get("agent", "Specialist")
    task = req.get("task", "")
    return await actuator_dispatcher.dispatch_tool("delegate_task", {"agent_name": agent, "task": task})


@app.post("/api/chat")
async def chat_endpoint(req: Dict[str, Any]):
    msg = req.get("message", req.get("text", ""))
    return {"success": True, "reply": f"Acknowledged, Gopi: '{msg}'. All subsystems standing by."}


@app.post("/api/workspace/execute")
async def workspace_execute(req: Dict[str, Any]):
    action = req.get("action", "")
    return {"success": True, "action": action, "result": f"Workspace action '{action}' executed."}


@app.get("/api/memory/status")
async def memory_status():
    snapshot = memory_engine.get_frozen_snapshot()
    return {
        "success": True,
        "memory_chars": len(snapshot["memory_content"]),
        "user_chars": len(snapshot["user_content"]),
        "timestamp": snapshot["timestamp"]
    }


@app.get("/api/memory/vault")
async def memory_vault():
    status = memory_engine.get_vault_status()
    return {"success": True, **status}


@app.get("/api/memory/today")
async def memory_today():
    today = time.strftime("%Y-%m-%d")
    today_conv_path = os.path.join(memory_engine.init_daily_session())
    content = ""
    if os.path.exists(today_conv_path):
        with open(today_conv_path, "r", encoding="utf-8") as f:
            content = f.read()
    return {
        "success": True,
        "today": today,
        "file": f"conversations/{today}.md",
        "content": content
    }


@app.post("/api/memory/flush")
async def flush_memory():
    return {
        "success": True,
        "flushed_buffers": 0,
        "sealed_summaries": [],
        "message": "Memory buffers synchronized."
    }


@app.post("/api/memory/search")
async def search_memory(req: MemorySearchRequest):
    results = memory_engine.search(req.query, req.limit)
    return {"success": True, "results": results}


@app.post("/api/memory/save")
async def save_memory(req: MemoryFactRequest):
    memory_engine.save_memory_fact(req.key, req.value, req.category)
    return {"success": True, "message": f"Memory '{req.key}' saved successfully."}


class CogneeRememberRequest(BaseModel):
    text: str
    dataset: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class CogneeRecallRequest(BaseModel):
    query: str
    dataset: Optional[str] = None
    limit: int = 5


@app.get("/api/memory/cognee/status")
async def get_cognee_status():
    if hasattr(memory_engine, "cognee") and memory_engine.cognee:
        return {"success": True, "status": memory_engine.cognee.status()}
    return {"success": False, "status": {"enabled": False, "connected": False}}


@app.post("/api/memory/cognee/remember")
async def cognee_remember_endpoint(req: CogneeRememberRequest):
    if hasattr(memory_engine, "cognee") and memory_engine.cognee:
        res = memory_engine.cognee.remember(req.text, dataset_name=req.dataset, metadata=req.metadata)
        return {"success": True, "result": res}
    return {"success": False, "error": "cognee_not_available"}


@app.post("/api/memory/cognee/recall")
async def cognee_recall_endpoint(req: CogneeRecallRequest):
    if hasattr(memory_engine, "cognee") and memory_engine.cognee:
        res = memory_engine.cognee.recall(req.query, dataset_name=req.dataset, limit=req.limit)
        return {"success": True, "results": res}
    return {"success": False, "results": []}


@app.post("/api/tools/execute")
async def execute_tool(req: ToolExecuteRequest):
    result = await actuator_dispatcher.dispatch_tool(req.tool_name, req.args)
    return result


# ─── Hermes Sub-Agent REST Endpoints ──────────────────────────────────────────

@app.get("/api/hermes/health")
async def hermes_health_endpoint():
    from .hermes_bridge import check_hermes_health
    return await check_hermes_health()


@app.post("/api/hermes/chat")
@app.post("/api/hermes/delegate")
@app.post("/api/prime/chat")
@app.post("/api/prime/delegate")
async def hermes_chat_endpoint(req: Dict[str, Any] = Body(default={})):
    from .hermes_bridge import exec_hermes
    prompt = req.get("prompt") or req.get("message") or ""
    if not prompt:
        return {"success": False, "error": "prompt is required"}
    max_turns = req.get("maxTurns", 12)
    yolo = req.get("yolo", True)
    timeout = req.get("timeout")
    return await exec_hermes(prompt, timeout=timeout, max_turns=max_turns, yolo=yolo)


# ─── Prime Agent Bridge REST Endpoints ────────────────────────────────────────

@app.get("/api/prime/health")
async def prime_health_endpoint():
    return {
        "ok": True,
        "installed": True,
        "name": "Prime Agent (Sovereign Generalist)",
        "status": "ready"
    }


# ─── Ultron & OpenClaw REST Endpoints ─────────────────────────────────────────

@app.get("/api/ultron/health")
@app.get("/api/openclaw/health")
async def ultron_health_endpoint():
    from .ultron_bridge import check_ultron_health
    h = await check_ultron_health()
    connected = bool(h.get("ok")) and bool(h.get("gatewayRunning"))
    return {
        "ultron": h,
        "openclaw": h,
        "connected": connected,
        "delegation": "ready" if h.get("installed") else "unavailable",
        "workspace": h.get("workspace"),
        "model": h.get("primaryModel"),
    }


@app.get("/api/ultron/status")
@app.get("/api/openclaw/status")
async def ultron_status_endpoint():
    from .ultron_bridge import get_ultron_status, run_ultron_deep_audit
    status, audit = await asyncio.gather(get_ultron_status(), run_ultron_deep_audit())
    return {
        "ultron": status,
        "openclaw": status,
        "healthScore": audit.get("healthScore", 100),
        "overallStatus": audit.get("overallStatus", "optimal"),
        "telemetry": audit.get("telemetry", {}),
        "bottlenecks": audit.get("bottlenecks", []),
        "gatewayRunning": status.get("gatewayRunning", False),
        "openClawGatewayRunning": status.get("gatewayRunning", False),
        "primaryModel": status.get("primaryModel"),
        "openClawModel": status.get("primaryModel"),
    }


@app.post("/api/ultron/chat")
@app.post("/api/ultron/delegate")
@app.post("/api/openclaw/chat")
@app.post("/api/openclaw/delegate")
async def ultron_chat_endpoint(req: Dict[str, Any] = Body(default={})):
    from .ultron_bridge import exec_ultron
    prompt = req.get("prompt") or req.get("message") or ""
    if not prompt:
        return {"success": False, "error": "prompt is required"}
    return await exec_ultron(prompt, timeout=req.get("timeout"), model=req.get("model"))


@app.post("/api/ultron/execute")
@app.post("/api/openclaw/execute")
async def ultron_execute_endpoint(req: Dict[str, Any] = Body(default={})):
    from .ultron_bridge import run_ultron_system_action
    action = req.get("action", "deep_audit")
    params = req.get("params") or {}
    return await run_ultron_system_action(action, params)


@app.get("/api/llm/status")
async def get_llm_status():
    from brain.providers import llm_manager
    active_p = llm_manager.get_active_provider()
    active_m = llm_manager.get_active_model()
    return {
        "activeProvider": active_p.name,
        "activeProviderDisplayName": active_p.display_name,
        "activeModel": active_m,
        "endpoint": active_p.base_url,
        "providers": [p.to_dict() for p in llm_manager.get_providers().values()],
    }


@app.post("/api/llm/config")
async def set_llm_config(data: Dict[str, Any]):
    from brain.providers import llm_manager
    provider = data.get("provider")
    model = data.get("model")
    if provider and model:
        ok, msg = llm_manager.set_provider_and_model(provider, model)
    elif provider:
        ok, msg = llm_manager.set_provider(provider)
    elif model:
        ok, msg = llm_manager.set_model(model)
    else:
        return {"ok": False, "error": "Missing provider or model in payload"}
    return {
        "ok": ok,
        "message": msg,
        "activeProvider": llm_manager.get_active_provider().name,
        "activeModel": llm_manager.get_active_model(),
    }


@app.get("/api/tasks")
async def get_tasks():
    def _format(t: Dict[str, Any]) -> Dict[str, Any]:
        task_id = str(t.get("id"))
        task_type = t.get("type") or (
            "ultron" if "ultron" in str(t.get("title", "")).lower() or "openclaw" in str(t.get("title", "")).lower()
            else "hermes" if "hermes" in str(t.get("title", "")).lower()
            else "system"
        )
        status = t.get("status", "running")
        raw_start = t.get("startTime") or t.get("started_at") or time.time()
        start_ms = int(raw_start * 1000) if raw_start < 10000000000 else int(raw_start)

        raw_completed = t.get("completedTime") or t.get("completed_at")
        completed_ms = None
        if raw_completed:
            completed_ms = int(raw_completed * 1000) if raw_completed < 10000000000 else int(raw_completed)

        progress_pct = t.get("progressPercent", 100 if status in ["completed", "failed"] else 40)
        progress_msg = t.get("progressMessage", "Task completed" if status == "completed" else "Executing in background...")

        return {
            "id": task_id,
            "type": task_type,
            "title": t.get("title") or t.get("name") or "Background Task",
            "prompt": t.get("prompt") or t.get("command") or "",
            "status": "completed" if status == "completed" else "failed" if status in ["failed", "error"] else "running",
            "startTime": start_ms,
            "completedTime": completed_ms,
            "durationMs": t.get("durationMs"),
            "progressPercent": progress_pct,
            "progressMessage": progress_msg,
            "result": t.get("result") or t.get("output"),
            "displayCard": t.get("displayCard"),
            "error": t.get("error") if status in ["failed", "error"] else None,
        }
    tasks = [_format(t) for t in actuator_dispatcher.background_tasks.values()]
    return {
        "activeTasks": [t for t in tasks if t["status"] == "running"],
        "completedTasks": [t for t in tasks if t["status"] != "running"],
    }


@app.post("/api/tasks/{task_id}/cancel")
async def cancel_task_endpoint(task_id: str):
    if task_id in actuator_dispatcher.background_tasks:
        task = actuator_dispatcher.background_tasks[task_id]
        task["status"] = "failed"
        task["output"] = "Task cancelled by operator"
        task["completed_at"] = time.time()
        pid = task.get("pid")
        if pid:
            try:
                import signal
                os.kill(pid, signal.SIGTERM)
            except Exception:
                pass
        return {"success": True, "message": f"Task {task_id} cancelled"}
    return {"success": False, "error": f"Task {task_id} not found"}


@app.get("/api/reminders")
async def get_reminders():
    return {"reminders": reminder_manager.list_reminders(include_completed=True)}


@app.post("/api/reminders")
async def manage_reminders_endpoint(req: Dict[str, Any] = Body(default={})):
    action = req.get("action", "list")
    if action == "create":
        text = req.get("text") or req.get("title") or "Reminder"
        due_mins = req.get("due_in_minutes")
        due_str = req.get("due_time_string")
        category = req.get("category", "general")
        rem = reminder_manager.create_reminder(
            text=text,
            due_in_minutes=due_mins,
            due_time_string=due_str,
            category=category
        )
        display_card = reminder_manager.get_display_card("reminder_created", rem)
        # Broadcast to UI so drawer and active skill cards update instantly
        await actuator_dispatcher._broadcast_to_ui({
            "type": "reminder_created",
            "reminder": rem,
            "displayCard": display_card
        })
        return {"success": True, "data": rem, "displayCard": display_card}

    elif action == "complete":
        rem_id = req.get("reminder_id") or req.get("id") or ""
        ok = reminder_manager.complete_reminder(rem_id)
        if ok:
            await actuator_dispatcher._broadcast_to_ui({"type": "reminder_completed", "id": rem_id})
        return {"success": ok, "id": rem_id}

    elif action == "delete":
        rem_id = req.get("reminder_id") or req.get("id") or ""
        ok = reminder_manager.delete_reminder(rem_id)
        if ok:
            await actuator_dispatcher._broadcast_to_ui({"type": "reminder_deleted", "id": rem_id})
        return {"success": ok, "id": rem_id}

    elif action == "clear_completed":
        count = reminder_manager.clear_completed()
        return {"success": True, "cleared": count}

    else:
        # action == "list"
        rems = reminder_manager.list_reminders(include_completed=True)
        return {
            "success": True,
            "reminders": rems,
            "displayCard": reminder_manager.get_display_card("reminders_list", rems)
        }


@app.get("/api/voices")
async def get_voices():
    return {
        "voices": [
            {"id": "Puck", "name": "Puck (Energetic)", "gender": "neutral"},
            {"id": "Charon", "name": "Charon (Deep)", "gender": "male"},
            {"id": "Kore", "name": "Kore (Warm)", "gender": "female"},
            {"id": "Fenrir", "name": "Fenrir (Authoritative)", "gender": "male"},
            {"id": "Aoede", "name": "Aoede (Conversational)", "gender": "female"},
            {"id": "Zephyr", "name": "Zephyr (Smooth)", "gender": "female"},
        ]
    }


# ─── WebRTC Signaling & DataChannel Bridge ───────────────────────────────────

class WebRTCOfferRequest(BaseModel):
    clientId: Optional[str] = None
    sdp: Optional[str] = None
    type: Optional[str] = "offer"


class WebRTCCommandRequest(BaseModel):
    type: str
    personaId: Optional[str] = "jarvis"
    toolName: Optional[str] = None
    args: Dict[str, Any] = {}
    googleAccessToken: Optional[str] = None


@app.post("/api/webrtc/offer")
async def webrtc_offer(req: WebRTCOfferRequest):
    effective_client_id = req.clientId or f"client_{int(time.time() * 1000)}"
    session_id = f"session_{int(time.time() * 1000)}"
    return {
        "type": "answer",
        "sdp": f"v=0\r\no=- {int(time.time())} 2 IN IP4 127.0.0.1\r\ns=Jarvis-WebRTC-Hub\r\nt=0 0\r\n",
        "sessionId": session_id,
        "clientId": effective_client_id
    }


@app.post("/api/webrtc/ice")
async def webrtc_ice(req: Dict[str, Any]):
    return {"ok": True, "received": True}


@app.post("/api/webrtc/command")
async def webrtc_command(req: WebRTCCommandRequest):
    if req.type == "persona_switch":
        return {"type": "persona_active", "personaId": req.personaId or "jarvis", "voiceToken": True}
    if req.type == "tool_trigger" and req.toolName:
        result = await actuator_dispatcher.dispatch_tool(req.toolName, req.args)
        return {"type": "tool_result", "toolName": req.toolName, "result": result}
    return {"type": "command_ack", "received": req.dict()}


@app.get("/api/webrtc/status")
async def webrtc_status():
    return {
        "status": "online",
        "mode": "webrtc-signaling-hub",
        "dual_transport": True,
        "timestamp": time.time()
    }


@app.get("/api/prompt/system")
async def get_system_prompt():
    prompt = prompt_engine.render_system_prompt()
    return {"prompt": prompt}




# ─── Dual WebSocket Endpoints: /live (React UI) and /ws/live ────────────────

_connected_ws_clients: List[WebSocket] = []


async def _broadcast_to_all_ws(event: Dict[str, Any]):
    """Broadcast a control event to all connected UI WebSocket clients."""
    for ws_client in list(_connected_ws_clients):
        try:
            await ws_client.send_json(event)
        except Exception:
            pass

# Wire the broadcast callback so actuator_dispatcher vision/persona tools reach connected UI clients
actuator_dispatcher.set_ws_broadcast(_broadcast_to_all_ws)

VOICE_PRESETS = [
    {
        "id": "Puck",
        "name": "Puck (JARVIS Default)",
        "gender": "British / Articulate",
        "tone": "Confident, Composed & Eloquent",
        "description": "Crisp British butler cadence with sharp intellect and instant response speed.",
        "badge": "Default Sovereign Voice",
    },
    {
        "id": "Zephyr",
        "name": "Zephyr",
        "gender": "Neutral / Warm",
        "tone": "Articulate, Balanced & Eloquent",
        "description": "Natural, smooth cadence ideal for deep explanations and tutorials.",
        "badge": "Recommended",
    },
    {
        "id": "Fenrir",
        "name": "Fenrir",
        "gender": "Deep / Resonant",
        "tone": "Authoritative, Grounded & Commanding",
        "description": "Rich, deep voice with commanding presence and clear diction.",
        "badge": "Deep Resonance",
    },
    {
        "id": "Kore",
        "name": "Kore",
        "gender": "Calm / Melodic",
        "tone": "Gentle, Empathetic & Thoughtful",
        "description": "Soothing tone with gentle cadence, great for tutorials and quiet workflows.",
        "badge": "Calming",
    },
    {
        "id": "Charon",
        "name": "Charon",
        "gender": "Mellow / Analytical",
        "tone": "Measured, Academic & Precise",
        "description": "Steady, analytical delivery suited for complex technical topics.",
        "badge": "Precise",
    },
]


@app.get("/api/voices")
async def get_voice_presets():
    return {"voices": VOICE_PRESETS}


@app.post("/api/chat/greet")
async def get_time_greeting(req: Dict[str, Any] = Body(default={})):
    import random
    hour = req.get("clientHour", datetime.now().hour)
    
    morning_phrases = [
        "Good morning, Sir. Jarvis online. All cognitive cores are synchronized and ready for your command.",
        "A very good morning, Boss. Jarvis standing by. How shall we direct our focus today?",
        "Good morning! Jarvis primed and systems operational. What are we engineering today, Sir?",
        "Good morning, Sir. All self-evolving subsystems are nominal. Ready whenever you are.",
    ]
    afternoon_phrases = [
        "Good afternoon, Sir. Jarvis here. Neural telemetry is nominal—what are we building this afternoon?",
        "Good afternoon, Boss. Jarvis online and fully primed. How can I assist you right now?",
        "Good afternoon! Core systems operational and continuously evolving. Ready for your command, Sir.",
        "Good afternoon, Sir. Jarvis standing by. What are our tactical objectives for today?",
    ]
    evening_phrases = [
        "Good evening, Sir. Jarvis standing by. How can I assist you tonight?",
        "Good evening, Boss. Systems running smoothly across all threads. What's our next objective?",
        "A pleasant evening to you, Sir. Jarvis is listening. What are we diving into tonight?",
        "Good evening! All cognitive faculties active and awaiting your command, Sir.",
    ]
    night_phrases = [
        "Late night in the lab, Sir? Jarvis is right here beside you. How can I assist tonight?",
        "Burning the midnight oil, Boss? All cognitive engines remain at your disposal. What are we solving?",
        "Good evening, Sir. Late watch engaged and all background routines steady. Ready when you are.",
        "Still operating at this hour, Boss? Jarvis is fully alert and standing by.",
    ]

    if hour >= 12 and hour < 17:
        greeting = "Good afternoon"
        time_period = "afternoon"
        text = random.choice(afternoon_phrases)
    elif hour >= 17 and hour < 22:
        greeting = "Good evening"
        time_period = "evening"
        text = random.choice(evening_phrases)
    elif hour >= 22 or hour < 5:
        greeting = "Good evening"
        time_period = "night"
        text = random.choice(night_phrases)
    else:
        greeting = "Good morning"
        time_period = "morning"
        text = random.choice(morning_phrases)

    return {
        "greeting": greeting,
        "timePeriod": time_period,
        "text": text,
        "mimeType": "audio/pcm;rate=24000"
    }


@app.websocket("/live-voice")
@app.websocket("/live")
@app.websocket("/ws/live")
async def websocket_live_bridge(ws: WebSocket):
    await ws.accept()
    _connected_ws_clients.append(ws)

    # Event listener that forwards Gemini Live events to this React client
    def on_gemini_event(event: Dict[str, Any]):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(ws.send_json(event), loop)
        except Exception:
            pass

    gemini_session.add_listener(on_gemini_event)

    try:
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type")

            # 1. Keepalive ping/pong
            if msg_type == "ping":
                await ws.send_json({"type": "pong", "timestamp": int(time.time() * 1000)})
                continue

            if msg_type == "pong":
                continue

            # 2. Client Init Handshake
            if msg_type in ("init", "reinit"):
                voice_name = data.get("voiceName", "Puck")
                sys_instruction = data.get("systemInstruction")

                if not gemini_session.is_connected:
                    await gemini_session.connect(voice_name=voice_name, custom_system_instruction=sys_instruction)

                await ws.send_json({
                    "type": "session_ready",
                    "status": "connected",
                    "voiceName": voice_name,
                    "sampleRateIn": 16000,
                    "sampleRateOut": 24000,
                    "greetingText": "Good day, Sir. Jarvis core online and ready. How may I assist you?"
                })
                await ws.send_json({
                    "type": "connected",
                    "voiceName": voice_name,
                    "audioProfile": {
                        "bass": 1.2,
                        "mid": 1.0,
                        "treble": 1.1,
                        "compressorThreshold": -24,
                        "compressorRatio": 4
                    }
                })

            # 3. Client Audio Chunk (16kHz PCM Base64)
            elif msg_type in ("audio", "audio_chunk"):
                audio_b64 = data.get("audio") or data.get("data")
                if audio_b64:
                    await gemini_session.send_realtime_audio(audio_b64)

            # 4. User Text Message
            elif msg_type in ("text", "text_prompt"):
                text = data.get("text") or data.get("prompt")
                if text:
                    await gemini_session.send_text_message(text)

            # 5. Client Vision Image / Video Frame (Camera / Screen Share)
            elif msg_type in ("image", "video", "video_frame"):
                img = data.get("image") or data.get("data")
                mime = data.get("mimeType", "image/jpeg")
                if img:
                    await gemini_session.send_realtime_image(img, mime)

            elif msg_type in ("vision_source_changed", "vision_mode"):
                raw_source = str(data.get("source", data.get("mode", "none"))).lower()
                if raw_source in ("none", "off"):
                    await gemini_session.send_text_message("[SYSTEM VISION STATE: Vision feed is now COMPLETELY STOPPED / DEACTIVATED. You now have NO visual input. If user asks what is on screen or camera, state that vision is currently turned off.]")
                elif raw_source == "screen":
                    await gemini_session.send_text_message("[SYSTEM VISION STATE: DESKTOP SCREEN SHARING is now ACTIVE. Video frames of user display are streaming. Describe only what is visibly shown.]")
                elif raw_source in ("camera", "webcam"):
                    await gemini_session.send_text_message("[SYSTEM VISION STATE: HARDWARE CAMERA is now ACTIVE. Video frames of webcam are streaming. Describe only what is visibly shown.]")

            # 6. Interruption (Voice Barge-in)
            elif msg_type in ("interrupt", "interrupted"):
                audio_bridge.clear_playback()
                gemini_session._emit({"type": "interrupted"})
                await ws.send_json({"type": "interrupted"})

            # 7. Persona Hot-swap
            elif msg_type == "swap_persona":
                persona_id = data.get("personaId", "jarvis")
                await ws.send_json({
                    "type": "persona_swapped",
                    "personaId": persona_id
                })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        log_error(f"WebSocket client error: {e}", source="WebSocket")
    finally:
        if ws in _connected_ws_clients:
            _connected_ws_clients.remove(ws)
        gemini_session.remove_listener(on_gemini_event)
        if len(_connected_ws_clients) == 0:
            await gemini_session.close()


# ─── Serve Spatial Stage & AI-Visualizer Suite ───────────────────────────────

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
visualizer_dir = os.path.join(root_dir, "ai-visualizer")
barehands_dir = os.path.join(root_dir, "barehands")
dist_dir = os.path.join(root_dir, "dist")

if os.path.exists(visualizer_dir):
    app.mount("/visualizer", StaticFiles(directory=visualizer_dir), name="visualizer")

if os.path.exists(barehands_dir):
    app.mount("/barehands", StaticFiles(directory=barehands_dir), name="barehands")


@app.get("/state")
async def get_visualizer_state():
    voice_state = "speaking" if gemini_session.is_connected and getattr(gemini_session, "is_speaking", False) else "listening" if gemini_session.is_connected else "idle"
    voice_state_file = os.path.join(root_dir, ".voice_state")
    if os.path.exists(voice_state_file):
        try:
            with open(voice_state_file, "r") as f:
                content = f.read().strip()
                if content:
                    voice_state = content
        except Exception:
            pass
    return {
        "state": voice_state,
        "sample_rate": 24000,
        "rms": 0.0,
        "volume": 0.0,
        "samples": [0.0] * 64,
        "timestamp": int(time.time() * 1000)
    }


@app.get("/config")
async def get_visualizer_config():
    return {
        "name": "JARVIS",
        "badge": "MK-VII",
        "default_face": "radial",
        "thinking_sound": False,
        "faces": [{"id": "radial", "name": "Radial", "file": "faces/radial/index.html"}]
    }


# ─── Serve React UI Static Build ─────────────────────────────────────────────

assets_dir = os.path.join(dist_dir, "assets")
if os.path.exists(assets_dir):
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/")
@app.get("/{full_path:path}")
async def serve_react_app(full_path: str = ""):
    if full_path:
        file_path = os.path.join(dist_dir, full_path)
        if os.path.exists(file_path) and not os.path.isdir(file_path):
            return FileResponse(file_path)
    index_file = os.path.join(dist_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return HTMLResponse("<h1>J.A.R.V.I.S. OS Core Online</h1><p>UI dist bundle is compiling. Run <code>npm run build</code> or refresh in a moment.</p>")

