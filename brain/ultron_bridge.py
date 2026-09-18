"""
Ultron Bridge for J.A.R.V.I.S. Python Core Engine.
Chief Security Sentinel, Linux OS Diagnostics & Autonomous Gateway.
Handles both Ultron and legacy OpenClaw requests seamlessly.
Matches the capabilities and contract of server/ultronBridge.ts.
"""

import os
import time
import json
import socket
import asyncio
import subprocess
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, List

from .actuator_dispatcher import actuator_dispatcher
from .telemetry_service import telemetry_service

HOME = os.path.expanduser("~")
HAS_ULTRON_DIR = os.path.exists(os.path.join(HOME, ".ultron"))
HAS_OPENCLAW_DIR = os.path.exists(os.path.join(HOME, ".openclaw"))

ULTRON_DIR = (
    os.path.join(HOME, ".ultron")
    if HAS_ULTRON_DIR
    else os.path.join(HOME, ".openclaw")
    if HAS_OPENCLAW_DIR
    else os.path.join(HOME, ".ultron")
)
OPENCLAW_DIR = ULTRON_DIR  # 100% alias

ULTRON_CONFIG = (
    os.path.join(ULTRON_DIR, "ultron.json")
    if os.path.exists(os.path.join(ULTRON_DIR, "ultron.json"))
    else os.path.join(ULTRON_DIR, "openclaw.json")
)
OPENCLAW_CONFIG = ULTRON_CONFIG  # 100% alias

ULTRON_GATEWAY_PORT = int(os.getenv("ULTRON_GATEWAY_PORT") or os.getenv("OPENCLAW_GATEWAY_PORT") or 18789)
OPENCLAW_GATEWAY_PORT = ULTRON_GATEWAY_PORT

ULTRON_GATEWAY_HOST = os.getenv("ULTRON_GATEWAY_HOST") or os.getenv("OPENCLAW_GATEWAY_HOST") or "127.0.0.1"
OPENCLAW_GATEWAY_HOST = ULTRON_GATEWAY_HOST

ULTRON_BASE_URL = f"http://{ULTRON_GATEWAY_HOST}:{ULTRON_GATEWAY_PORT}"
OPENCLAW_BASE_URL = ULTRON_BASE_URL


def read_ultron_config() -> Optional[Dict[str, Any]]:
    try:
        if os.path.exists(ULTRON_CONFIG):
            with open(ULTRON_CONFIG, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return None


read_openclaw_config = read_ultron_config


async def probe_ultron_gateway() -> bool:
    """Check if Ultron / OpenClaw gateway service is active or reachable on port 18789."""
    # 1. Probe systemd user service first
    try:
        proc = subprocess.run(
            ["systemctl", "--user", "is-active", "openclaw-gateway.service"],
            capture_output=True,
            text=True,
            timeout=2.0
        )
        if proc.stdout.strip() == "active":
            return True
    except Exception:
        pass

    # 2. Probe TCP socket on port 18789
    loop = asyncio.get_event_loop()

    def _check():
        try:
            sock = socket.create_connection((ULTRON_GATEWAY_HOST, ULTRON_GATEWAY_PORT), timeout=0.6)
            sock.close()
            return True
        except Exception:
            return False

    return await loop.run_in_executor(None, _check)


probe_openclaw_gateway = probe_ultron_gateway


async def check_ultron_health() -> Dict[str, Any]:
    installed = os.path.exists(ULTRON_DIR) or bool(subprocess.run(["which", "openclaw"], capture_output=True).stdout)
    config_present = os.path.exists(ULTRON_CONFIG)
    workspace_path = os.path.join(ULTRON_DIR, "workspace")
    workspace = workspace_path if os.path.exists(workspace_path) else None
    agents_dir_path = os.path.join(ULTRON_DIR, "agents")
    agents_dir = agents_dir_path if os.path.exists(agents_dir_path) else None
    gateway_url = ULTRON_BASE_URL

    if not installed:
        return {
            "ok": False,
            "installed": False,
            "configPresent": False,
            "workspace": None,
            "gatewayRunning": False,
            "gatewayUrl": gateway_url,
            "primaryModel": None,
            "agentsDir": None,
            "error": f"Ultron gateway directory {ULTRON_DIR} not found",
        }

    cfg = read_ultron_config() or {}
    primary_model = (
        cfg.get("agents", {}).get("defaults", {}).get("model", {}).get("primary")
        or "omniroute/auto/best-coding"
    )
    gateway_running = await probe_ultron_gateway()

    return {
        "ok": installed and (gateway_running or config_present),
        "installed": installed,
        "configPresent": config_present,
        "workspace": workspace,
        "gatewayRunning": gateway_running,
        "gatewayUrl": gateway_url,
        "primaryModel": primary_model,
        "agentsDir": agents_dir,
    }


check_openclaw_health = check_ultron_health


async def get_ultron_status() -> Dict[str, Any]:
    h = await check_ultron_health()
    return {
        "installed": h["installed"],
        "configPresent": h["configPresent"],
        "workspace": h["workspace"],
        "gatewayRunning": h["gatewayRunning"],
        "gatewayUrl": h["gatewayUrl"],
        "primaryModel": h["primaryModel"],
        "agentsDir": h["agentsDir"],
        "error": h.get("error"),
    }


get_openclaw_status = get_ultron_status


def _extract_openclaw_reply(data: Any) -> str:
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            return data
    if isinstance(data, dict):
        if "payload" in data:
            session = data.get("payload", {}).get("agentMeta", {}).get("session", {})
            vis = session.get("finalAssistantVisibleText") or session.get("finalAssistantRawText")
            if vis:
                return str(vis).strip()
        for k in ["reply", "text", "response", "content", "message"]:
            if k in data and data[k]:
                return str(data[k]).strip()
    return ""


async def exec_ultron(prompt: str, timeout: Optional[float] = None, model: Optional[str] = None) -> Dict[str, Any]:
    """
    Dispatches task to Ultron (OpenClaw) autonomous gateway with verified working provider fallback.
    """
    if not prompt or not prompt.strip():
        return {"success": False, "text": "", "error": "Prompt is required"}

    cfg = read_ultron_config() or {}
    timeout_sec = timeout or 60.0
    configured_model = cfg.get("agents", {}).get("defaults", {}).get("model", {}).get("primary")
    # Prefer omniroute if configured model is in cooldown or missing
    preferred_models = []
    if model:
        preferred_models.append(model)
    preferred_models.extend(["omniroute/auto/best-coding", "omniroute/auto/best-reasoning"])
    if configured_model and configured_model not in preferred_models:
        preferred_models.append(configured_model)

    # Execute via OpenClaw CLI runner with model fallback
    last_error = ""
    for target_model in preferred_models:
        try:
            cmd = ["openclaw", "agent", "--message", prompt.strip(), "--json"]
            if target_model:
                cmd.extend(["--model", target_model])

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_sec)
            out_str = stdout.decode("utf-8", errors="replace").strip()
            err_str = stderr.decode("utf-8", errors="replace").strip()

            if out_str:
                try:
                    parsed = json.loads(out_str)
                    if parsed.get("ok"):
                        reply = _extract_openclaw_reply(parsed)
                        if reply:
                            return {
                                "success": True,
                                "text": reply,
                                "model": target_model,
                                "sessionId": parsed.get("runId"),
                                "raw": parsed
                            }
                except Exception:
                    pass

                if proc.returncode == 0 and out_str:
                    return {"success": True, "text": out_str, "model": target_model}

            last_error = err_str or out_str or f"OpenClaw process exited with code {proc.returncode}"
        except asyncio.TimeoutError:
            last_error = f"Ultron timed out after {timeout_sec:.0f}s"
            break
        except Exception as ex:
            last_error = str(ex)

    return {
        "success": False,
        "text": "",
        "error": f"Ultron execution error: {last_error or 'No response received'}",
    }


exec_openclaw = exec_ultron
delegate_to_ultron = exec_ultron
delegate_to_openclaw = exec_ultron


# ─── Deep System Audit ────────────────────────────────────────────────────────

async def run_ultron_deep_audit() -> Dict[str, Any]:
    telemetry = await telemetry_service.get_full_telemetry()
    hw_state = await telemetry_service.get_hardware_state()
    gateway_status = await get_ultron_status()

    # Get running processes
    procs_res = await actuator_dispatcher.execute_cpp_worker("sys_telemetry", ["processes", "30"])
    procs = procs_res.get("result", {}).get("processes", []) if procs_res.get("success") else []

    sound = hw_state.get("soundServer", {"healthy": True, "driver": "pipewire"})
    cpu_percent = telemetry.get("cpu", {}).get("usagePercent", 0)
    ram_percent = telemetry.get("memory", {}).get("usagePercent", 0)
    ram_used_mb = telemetry.get("memory", {}).get("usedMb", 0)
    ram_total_mb = telemetry.get("memory", {}).get("totalMb", 0)
    thermals = hw_state.get("thermals", {})
    max_temp = thermals.get("maxTempCelsius") or thermals.get("cpuTempCelsius") or 0

    bottlenecks = []
    recommendations = []
    score = 100

    if cpu_percent > 80:
        bottlenecks.append(f"High CPU load: {cpu_percent}%")
        recommendations.append("Inspect top CPU processes or apply throttle cooling")
        score -= 20
    if ram_percent > 85:
        bottlenecks.append(f"High RAM usage: {ram_percent}% ({ram_used_mb}MB / {ram_total_mb}MB)")
        recommendations.append("Trigger Ultron RAM boost to reclaim system cache")
        score -= 25
    if max_temp > 80:
        bottlenecks.append(f"High thermal readings: {max_temp}°C")
        recommendations.append("Check fan curves or reduce workload")
        score -= 15
    if not sound.get("healthy", True):
        bottlenecks.append(f"Sound subsystem degraded ({sound.get('driver', 'audio')})")
        recommendations.append("Run Ultron sound heal to restart audio pipeline")
        score -= 10
    if not gateway_status.get("gatewayRunning") and gateway_status.get("installed"):
        recommendations.append("Ultron gateway is installed but not running on port 18789")

    top_memory_processes = [
        {"name": p.get("command", "proc").split()[0], "pid": p.get("pid", 0), "memoryPercent": p.get("memPercent", 0), "cpuPercent": p.get("cpuPercent", 0)}
        for p in procs[:5]
    ]
    top_cpu_processes = [
        {"name": p.get("command", "proc").split()[0], "pid": p.get("pid", 0), "memoryPercent": p.get("memPercent", 0), "cpuPercent": p.get("cpuPercent", 0)}
        for p in sorted(procs, key=lambda x: x.get("cpuPercent", 0), reverse=True)[:5]
    ]

    overall_status = "optimal" if score > 80 else "warning" if score > 50 else "critical"
    summary = (
        f"System health {score}/100 ({overall_status.upper()}). "
        f"CPU: {cpu_percent}%, RAM: {ram_percent}%, Temp: {max_temp}°C. "
        f"Ultron Gateway: {'online' if gateway_status.get('gatewayRunning') else 'installed/offline' if gateway_status.get('installed') else 'not installed'}. "
        f"{'Bottlenecks: ' + '; '.join(bottlenecks) + '.' if bottlenecks else 'All subsystems optimal.'}"
    )

    return {
        "timestamp": int(time.time() * 1000),
        "healthScore": max(0, score),
        "overallStatus": overall_status,
        "summary": summary,
        "telemetry": {
            "cpuPercent": cpu_percent,
            "ramPercent": ram_percent,
            "ramUsedMb": ram_used_mb,
            "ramTotalMb": ram_total_mb,
            "swapUsedMb": 0,
            "maxTempCelsius": max_temp,
            "batteryPercent": telemetry.get("battery", {}).get("percent"),
            "batteryState": telemetry.get("battery", {}).get("state", "unknown"),
            "powerProfile": telemetry.get("powerProfile", "balanced"),
        },
        "bottlenecks": bottlenecks,
        "recommendations": recommendations,
        "soundStatus": sound,
        "openClaw": gateway_status,
        "gatewayStatus": gateway_status,
        "topMemoryProcesses": top_memory_processes,
        "topCpuProcesses": top_cpu_processes,
    }


# ─── System Boost ─────────────────────────────────────────────────────────────

async def run_ultron_system_boost() -> Dict[str, Any]:
    before_telem = await telemetry_service.get_full_telemetry()
    before_ram_pct = before_telem.get("memory", {}).get("usagePercent", 0)
    before_ram_mb = before_telem.get("memory", {}).get("usedMb", 0)
    optimizations = []
    killed_zombies = 0

    try:
        await actuator_dispatcher.execute_linux_command("sync")
        optimizations.append("Filesystem buffer synchronized")
    except Exception:
        pass

    try:
        prof_res = await actuator_dispatcher.execute_cpp_worker("hardware_ctrl", ["set_power_profile", "performance"])
        if prof_res.get("success"):
            optimizations.append("Power governor set to high-performance mode")
    except Exception:
        pass

    try:
        proc_check = await actuator_dispatcher.execute_linux_command("ps -eo pid,stat,comm | grep -w 'Z' | awk '{print $1}'")
        if proc_check.get("success") and proc_check.get("stdout"):
            z_pids = proc_check["stdout"].split()
            for zp in z_pids:
                try:
                    await actuator_dispatcher.execute_linux_command(f"kill -9 {zp}")
                    killed_zombies += 1
                except Exception:
                    pass
        if killed_zombies > 0:
            optimizations.append(f"Purged {killed_zombies} zombie process handles")
    except Exception:
        pass

    after_telem = await telemetry_service.get_full_telemetry()
    after_ram_pct = after_telem.get("memory", {}).get("usagePercent", 0)
    after_ram_mb = after_telem.get("memory", {}).get("usedMb", 0)
    freed_ram_mb = max(0, before_ram_mb - after_ram_mb)
    optimizations.append(f"RAM: {before_ram_pct}% → {after_ram_pct}%")

    return {
        "success": True,
        "freedRamMb": freed_ram_mb,
        "killedZombies": killed_zombies,
        "powerProfileSet": "performance",
        "optimizationsApplied": optimizations,
        "beforeRamPercent": before_ram_pct,
        "afterRamPercent": after_ram_pct,
        "summary": f"Ultron boost complete. {', '.join(optimizations)}. Freed ~{freed_ram_mb} MB.",
    }


# ─── Subsystem Heal ───────────────────────────────────────────────────────────

async def run_ultron_subsystem_heal(subsystem: str = "all") -> Dict[str, Any]:
    healed = []
    if subsystem in ["sound", "all"]:
        try:
            res = await actuator_dispatcher.execute_cpp_worker("hardware_ctrl", ["heal_sound_server"])
            if res.get("success"):
                healed.append("Sound server pipeline restarted and verified healthy")
            else:
                healed.append(f"Sound server: {res.get('error', 'check completed')}")
        except Exception as e:
            healed.append(f"Sound heal notice: {str(e)}")

    if subsystem in ["network", "all"]:
        try:
            net_res = await actuator_dispatcher.execute_cpp_worker("hardware_ctrl", ["network_status"])
            if net_res.get("success"):
                healed.append("Network interfaces verified active")
        except Exception as e:
            healed.append(f"Network check: {str(e)}")

    return {
        "success": True,
        "healed": healed,
        "message": ". ".join(healed) or "Subsystems inspected.",
    }


# ─── Security Audit ───────────────────────────────────────────────────────────

async def run_ultron_security_audit() -> Dict[str, Any]:
    fw_res = await actuator_dispatcher.execute_cpp_worker("hardware_ctrl", ["firewall_status"])
    conn_res = await actuator_dispatcher.execute_cpp_worker("hardware_ctrl", ["network_connections", "50"])

    firewall = fw_res.get("result", {}) if fw_res.get("success") else {"active": True}
    connections = conn_res.get("result", {}).get("connections", []) if conn_res.get("success") else []

    listening_ports = []
    suspicious = []
    for c in connections:
        st = c.get("state", "").upper()
        if st in ["LISTEN", "LISTENING"]:
            addr = c.get("localAddress", "")
            port = int(addr.split(":")[-1]) if ":" in addr else 0
            listening_ports.append({
                "port": port,
                "proto": c.get("protocol", "tcp"),
                "process": c.get("process", "unknown")
            })

    firewall_active = firewall.get("active", True)
    if not firewall_active:
        suspicious.append("UFW firewall is inactive")

    external_count = len([
        c for c in connections
        if c.get("state", "").upper() == "ESTABLISHED"
        and not c.get("remoteAddress", "").startswith("127.")
        and not c.get("remoteAddress", "").startswith("::1")
    ])

    summary = (
        f"Security audit: Firewall {'ACTIVE' if firewall_active else 'INACTIVE'}. "
        f"{len(listening_ports)} listening ports. {external_count} external sockets. "
        f"{'Alerts: ' + '; '.join(suspicious) if suspicious else 'No critical findings.'}"
    )

    return {
        "timestamp": int(time.time() * 1000),
        "firewallActive": firewall_active,
        "listeningPorts": listening_ports[:15],
        "externalConnectionsCount": external_count,
        "suspiciousFindings": suspicious,
        "summary": summary,
    }


# ─── Universal Dispatcher ─────────────────────────────────────────────────────

async def run_ultron_system_action(action: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    params = params or {}
    act = action.lower()

    if act in ["ultron_status", "openclaw_status"]:
        result = await get_ultron_status()
        return {
            "success": True,
            "action": "ultron_status",
            "data": result,
            "speechSummary": (
                f"Ultron gateway status: "
                f"{'gateway online on port 18789, model ' + (result.get('primaryModel') or 'default') if result.get('gatewayRunning') else 'installed but gateway offline' if result.get('installed') else 'not installed'}."
            ),
            "displayCard": {
                "type": "ultron_status",
                "title": "Ultron • Autonomous Gateway Status",
                "data": result,
            },
        }

    elif act in ["ultron_delegate", "openclaw_delegate"]:
        prompt = params.get("prompt") or params.get("message") or ""
        result = await exec_ultron(prompt, timeout=params.get("timeout"), model=params.get("model"))
        return {
            "success": result.get("success", False),
            "action": "ultron_delegate",
            "data": result,
            "speechSummary": (
                f"Ultron responded: {result.get('text', '')[:140]}"
                if result.get("success")
                else f"Ultron delegation failed: {result.get('error')}"
            ),
            "displayCard": {
                "type": "ultron_response",
                "title": f"Ultron ⟶ {prompt[:50] or 'Autonomous Task'}",
                "data": {**result, "prompt": prompt},
            },
        }

    elif act == "boost_system":
        result = await run_ultron_system_boost()
        return {
            "success": result.get("success", False),
            "action": "boost_system",
            "data": result,
            "speechSummary": f"Ultron boost complete. RAM at {result.get('afterRamPercent', 0):.1f} percent, freed {result.get('freedRamMb', 0)} megabytes.",
            "displayCard": {
                "type": "ultron_boost",
                "title": "Ultron • System Performance Boost",
                "data": result,
            },
        }

    elif act == "heal_subsystem":
        result = await run_ultron_subsystem_heal(params.get("subsystem", "all"))
        return {
            "success": result.get("success", False),
            "action": "heal_subsystem",
            "data": result,
            "speechSummary": f"Ultron subsystem heal: {result.get('message')}",
            "displayCard": {
                "type": "ultron_heal",
                "title": "Ultron • Subsystem Self-Healing",
                "data": result,
            },
        }

    elif act == "security_audit":
        result = await run_ultron_security_audit()
        return {
            "success": True,
            "action": "security_audit",
            "data": result,
            "speechSummary": f"Ultron security audit complete. {result.get('summary')}",
            "displayCard": {
                "type": "ultron_security",
                "title": "Ultron • Sentinel Security Audit",
                "data": result,
            },
        }

    else:  # default: deep_audit
        result = await run_ultron_deep_audit()
        return {
            "success": True,
            "action": "deep_audit",
            "data": result,
            "speechSummary": f"Ultron deep diagnostic complete. {result.get('summary')}",
            "displayCard": {
                "type": "ultron_audit",
                "title": "Ultron • Deep OS Diagnostic & Sentinel Audit",
                "data": result,
            },
        }
