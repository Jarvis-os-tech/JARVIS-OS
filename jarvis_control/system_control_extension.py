"""Extended system control actions backed by jarvis_os_bridge.

Provides WiFi, Bluetooth, network status, process management, and screenshot
tools that the voice agent can invoke through the existing Executor policy.
All actions use native DBus where possible and verify state after mutations.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("jarvis.control.extension")

# Thread pool for running async bridge calls from sync executor context
_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="bridge")


def _run_async(coro):
    """Run an async coroutine from a synchronous context safely."""
    return _POOL.submit(asyncio.run, coro).result(timeout=30)


EXTENSION_ACTIONS = (
    # Network
    'network_status', 'wifi_scan', 'wifi_connect', 'wifi_disconnect',
    'wifi_forget', 'wifi_saved',
    'vpn_connect', 'vpn_disconnect', 'vpn_list',
    # Bluetooth deep control
    'bt_status', 'bt_scan', 'bt_pair', 'bt_connect', 'bt_disconnect',
    'bt_remove', 'bt_devices', 'bt_audio_route',
    # Process management
    'process_list', 'process_kill',
    # Screenshot
    'screenshot_full', 'screenshot_region', 'screenshot_window',
)

SCHEMA = {
    'name': 'system_control_extension',
    'description': (
        'Deep OS integration tools for WiFi management (scan, connect, disconnect, forget, saved networks), '
        'Bluetooth device management (scan, pair, connect, disconnect, remove, audio routing), '
        'VPN control (connect, disconnect, list), full network status (IP, gateway, interface details), '
        'process management (list top processes, kill by name or PID), '
        'and screenshots (full screen, region selection, active window). '
        'Use system_control for basic toggles (bluetooth on/off, volume, brightness). '
        'Use system_control_extension for deeper operations like WiFi network selection, '
        'Bluetooth device pairing, or taking screenshots.'
    ),
    'input_schema': {
        'type': 'object',
        'properties': {
            'action': {
                'type': 'string',
                'enum': list(EXTENSION_ACTIONS),
            },
            'target': {
                'type': 'string',
                'description': (
                    'Target identifier: SSID for wifi_connect/wifi_forget, '
                    'device name/address for bt_connect/bt_disconnect/bt_pair/bt_remove/bt_audio_route, '
                    'VPN profile name for vpn_connect/vpn_disconnect, '
                    'process name or PID for process_kill.'
                ),
            },
            'password': {
                'type': 'string',
                'description': 'WiFi password for wifi_connect (optional for saved/open networks).',
            },
        },
        'required': ['action'],
        'additionalProperties': False,
    },
}


class SystemControlExtensionError(ValueError):
    pass


def validate(action: str, target: str = '', password: str = '') -> Optional[str]:
    """Return an argument error without touching the system."""
    if action not in EXTENSION_ACTIONS:
        return 'Unknown extension action; choose one of: ' + ', '.join(EXTENSION_ACTIONS)
    if action in ('wifi_connect', 'wifi_forget', 'bt_connect', 'bt_disconnect',
                   'bt_pair', 'bt_remove', 'bt_audio_route',
                   'vpn_connect', 'vpn_disconnect', 'process_kill'):
        if not target or not isinstance(target, str) or not target.strip():
            return f'target is required for {action}'
    return None


def _run_cmd(cmd: List[str], timeout: float = 10.0) -> Tuple[int, str, str]:
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return res.returncode, res.stdout.strip(), res.stderr.strip()
    except Exception as exc:
        return 1, "", str(exc)


def execute(executor, action: str, target: str = '', password: str = '') -> Any:
    """Execute an extended system control action and return a verified Result."""
    from .tools import Result

    try:
        target = target.strip() if target else ''

        # ── Network Actions ──
        if action == 'network_status':
            from jarvis_os_bridge.network_control import NetworkController
            result = _run_async(NetworkController().get_status())
            if not result.get('ok'):
                return Result(False, result.get('error', 'Network status unavailable'))
            wifi = result.get('wifi') or {}
            parts = [
                f"State: {result.get('state', 'unknown')}",
                f"Connectivity: {result.get('connectivity', 'unknown')}",
                f"IP: {', '.join(result.get('ip_addresses', [])) or 'none'}",
            ]
            if wifi.get('connected'):
                parts.append(f"WiFi: {wifi.get('ssid')} ({wifi.get('signal_percent')}% on {wifi.get('interface')})")
            else:
                parts.append("WiFi: disconnected")
            return Result(True, '. '.join(parts) + '.')

        if action == 'wifi_scan':
            from jarvis_os_bridge.network_control import NetworkController
            aps = _run_async(NetworkController().scan_wifi(rescan=True))
            if not aps:
                return Result(True, 'No WiFi networks found nearby.')
            lines = [f"Found {len(aps)} WiFi networks:"]
            for ap in aps[:15]:
                lines.append(f"  {ap['ssid']} — {ap['signal_percent']}% signal, {ap['security']}, {ap['band']}")
            return Result(True, '\n'.join(lines))

        if action == 'wifi_connect':
            from jarvis_os_bridge.network_control import NetworkController
            ctrl = NetworkController()
            result = _run_async(ctrl.connect_wifi(target, password or None))
            if result.get('ok'):
                return Result(True, result.get('message', f"Connected to '{target}'."))
            return Result(False, result.get('error', f"Failed connecting to '{target}'"))

        if action == 'wifi_disconnect':
            from jarvis_os_bridge.network_control import NetworkController
            result = _run_async(NetworkController().disconnect_wifi())
            return Result(result.get('ok', False), result.get('message') or result.get('error', 'WiFi disconnect attempted.'))

        if action == 'wifi_forget':
            from jarvis_os_bridge.network_control import NetworkController
            result = _run_async(NetworkController().forget_wifi(target))
            return Result(result.get('ok', False), result.get('message') or result.get('error', ''))

        if action == 'wifi_saved':
            from jarvis_os_bridge.network_control import NetworkController
            saved = _run_async(NetworkController().list_saved_wifi())
            if not saved:
                return Result(True, 'No saved WiFi networks.')
            lines = [f"Saved WiFi networks ({len(saved)}):"]
            for s in saved:
                lines.append(f"  {s['name']}")
            return Result(True, '\n'.join(lines))

        if action == 'vpn_list':
            from jarvis_os_bridge.network_control import NetworkController
            vpns = _run_async(NetworkController().list_vpns())
            if not vpns:
                return Result(True, 'No VPN profiles configured.')
            lines = [f"VPN profiles ({len(vpns)}):"]
            for v in vpns:
                status = "active" if v.get('active') else "inactive"
                lines.append(f"  {v['name']} ({v['type']}) — {status}")
            return Result(True, '\n'.join(lines))

        if action == 'vpn_connect':
            from jarvis_os_bridge.network_control import NetworkController
            result = _run_async(NetworkController().connect_vpn(target))
            return Result(result.get('ok', False), result.get('message') or result.get('error', ''))

        if action == 'vpn_disconnect':
            from jarvis_os_bridge.network_control import NetworkController
            result = _run_async(NetworkController().disconnect_vpn(target))
            return Result(result.get('ok', False), result.get('message') or result.get('error', ''))

        # ── Bluetooth Actions ──
        if action in ('bt_status', 'bt_devices'):
            from jarvis_os_bridge.bluetooth_control import BluetoothController
            status = _run_async(BluetoothController().get_status())
            if not status.get('ok'):
                return Result(False, status.get('error', 'Bluetooth status unavailable'))
            devs = status.get('devices', [])
            parts = [
                f"Bluetooth: {'ON' if status.get('powered') else 'OFF'}",
                f"Adapter: {status.get('adapter', 'unknown')}",
                f"Known devices ({len(devs)}):",
            ]
            for d in devs:
                conn = "Connected" if d.get('connected') else "Disconnected"
                bat = f", Battery {d['battery_percent']}%" if d.get('battery_percent') is not None else ""
                parts.append(f"  {d.get('name')} [{d.get('address')}] ({conn}{bat})")
            return Result(True, '\n'.join(parts))

        if action == 'bt_scan':
            from jarvis_os_bridge.bluetooth_control import BluetoothController
            devs = _run_async(BluetoothController().scan_devices(timeout=6.0))
            if not devs:
                return Result(True, 'No Bluetooth devices found nearby.')
            lines = [f"Found {len(devs)} Bluetooth devices:"]
            for d in devs:
                conn = "Connected" if d.get('connected') else ""
                lines.append(f"  {d.get('name', 'Unknown')} [{d.get('address')}] {conn}")
            return Result(True, '\n'.join(lines))

        if action == 'bt_connect':
            from jarvis_os_bridge.bluetooth_control import BluetoothController
            result = _run_async(BluetoothController().connect_device(target))
            return Result(result.get('ok', False), result.get('message') or result.get('error', ''))

        if action == 'bt_disconnect':
            from jarvis_os_bridge.bluetooth_control import BluetoothController
            result = _run_async(BluetoothController().disconnect_device(target))
            return Result(result.get('ok', False), result.get('message') or result.get('error', ''))

        if action == 'bt_pair':
            from jarvis_os_bridge.bluetooth_control import BluetoothController
            result = _run_async(BluetoothController().pair_device(target))
            return Result(result.get('ok', False), result.get('message') or result.get('error', ''))

        if action == 'bt_remove':
            from jarvis_os_bridge.bluetooth_control import BluetoothController
            result = _run_async(BluetoothController().remove_device(target))
            return Result(result.get('ok', False), result.get('message') or result.get('error', ''))

        if action == 'bt_audio_route':
            from jarvis_os_bridge.bluetooth_control import BluetoothController
            result = _run_async(BluetoothController().route_audio(target))
            return Result(result.get('ok', False), result.get('message') or result.get('error', ''))

        # ── Process Management ──
        if action == 'process_list':
            code, out, _ = _run_cmd(['ps', '-eo', 'pid,pcpu,pmem,rss,comm', '--sort=-pcpu', '--no-headers'])
            if code != 0:
                return Result(False, 'Could not list processes')
            lines = ["PID      CPU%  MEM%  RSS(MB) COMMAND"]
            for line in out.splitlines()[:20]:
                parts = line.split(None, 4)
                if len(parts) >= 5:
                    rss_mb = int(parts[3]) / 1024
                    lines.append(f"  {parts[0]:>7} {parts[1]:>5} {parts[2]:>5} {rss_mb:>7.1f} {parts[4]}")
            return Result(True, '\n'.join(lines))

        if action == 'process_kill':
            # Resolve target — could be PID or name
            if target.isdigit():
                pid = int(target)
                # Verify process exists
                code, out, _ = _run_cmd(['ps', '-p', str(pid), '-o', 'comm='])
                if code != 0:
                    return Result(False, f'No process found with PID {pid}')
                proc_name = out.strip()
                code, _, err = _run_cmd(['kill', str(pid)])
                if code == 0:
                    return Result(True, f'Sent SIGTERM to {proc_name} (PID {pid}).')
                return Result(False, err or f'Failed to kill PID {pid}')
            else:
                # Kill by name
                code, out, _ = _run_cmd(['pgrep', '-x', target])
                if code != 0:
                    # Try partial match
                    code, out, _ = _run_cmd(['pgrep', '-f', target])
                if code != 0:
                    return Result(False, f"No process found matching '{target}'")
                pids = out.strip().splitlines()[:5]  # Limit to 5
                killed = []
                for p in pids:
                    kc, _, _ = _run_cmd(['kill', p.strip()])
                    if kc == 0:
                        killed.append(p.strip())
                if killed:
                    return Result(True, f"Sent SIGTERM to '{target}' (PIDs: {', '.join(killed)}).")
                return Result(False, f"Failed to kill any process matching '{target}'")

        # ── Screenshot ──
        if action.startswith('screenshot_'):
            if not shutil.which('grim'):
                return Result(False, 'Screenshot tool (grim) is not installed')

            screenshots_dir = Path.home() / "Pictures" / "Screenshots"
            screenshots_dir.mkdir(parents=True, exist_ok=True)
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            output_path = screenshots_dir / f"jarvis-screenshot-{timestamp}.png"

            if action == 'screenshot_full':
                code, _, err = _run_cmd(['grim', str(output_path)], timeout=5.0)
                if code == 0:
                    return Result(True, f'Full screenshot saved to {output_path}.')
                return Result(False, err or 'Screenshot failed')

            elif action == 'screenshot_region':
                if not shutil.which('slurp'):
                    return Result(False, 'Region selection tool (slurp) is not installed')
                # slurp provides interactive region selection
                slurp = subprocess.run(['slurp'], capture_output=True, text=True, timeout=30)
                if slurp.returncode != 0:
                    return Result(False, 'Region selection cancelled')
                geometry = slurp.stdout.strip()
                code, _, err = _run_cmd(['grim', '-g', geometry, str(output_path)], timeout=5.0)
                if code == 0:
                    return Result(True, f'Region screenshot saved to {output_path}.')
                return Result(False, err or 'Region screenshot failed')

            elif action == 'screenshot_window':
                # Capture active window geometry from hyprctl
                hypr = subprocess.run(['hyprctl', '-j', 'activewindow'], capture_output=True, text=True, timeout=2)
                if hypr.returncode != 0:
                    return Result(False, 'Could not query active window')
                try:
                    win = json.loads(hypr.stdout)
                    at = win.get('at', [0, 0])
                    size = win.get('size', [800, 600])
                    geometry = f"{at[0]},{at[1]} {size[0]}x{size[1]}"
                except (json.JSONDecodeError, TypeError):
                    return Result(False, 'Invalid window geometry from compositor')
                code, _, err = _run_cmd(['grim', '-g', geometry, str(output_path)], timeout=5.0)
                if code == 0:
                    title = win.get('title') or win.get('class') or 'window'
                    return Result(True, f'Screenshot of {title} saved to {output_path}.')
                return Result(False, err or 'Window screenshot failed')

        return Result(False, f'Unhandled extension action: {action}')

    except SystemControlExtensionError as error:
        return Result(False, str(error))
    except concurrent.futures.TimeoutError:
        return Result(False, f'Extension action {action} timed out after 30s')
    except Exception as error:
        log.warning("Extension action %s failed: %s", action, error)
        return Result(False, f'Extension action failed: {error}')
