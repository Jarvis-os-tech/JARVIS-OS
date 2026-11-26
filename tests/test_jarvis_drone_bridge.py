import pytest
import asyncio
import json
import socket
import websockets
from shell.drone.bridge import DroneBridge

def get_free_port() -> int:
    """Dynamically allocate an ephemeral port to prevent address collision."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

@pytest.mark.asyncio
async def test_bridge_broadcast_state_and_gesture():
    port = get_free_port()
    bridge = DroneBridge(host="127.0.0.1", port=port)
    server_task = asyncio.create_task(bridge.start())
    await asyncio.sleep(0.1)

    try:
        async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
            # Broadcast state
            await bridge.broadcast_state("listening")
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            assert msg == {"version": "1.0", "type": "STATE", "state": "listening"}

            # Broadcast gesture
            await bridge.broadcast_gesture("nod")
            msg2 = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            assert msg2 == {"version": "1.0", "type": "GESTURE", "name": "nod"}

            # Send tap from client to bridge
            taps = []
            bridge.register_tap_handler(lambda: taps.append(True))
            await ws.send(json.dumps({"event": "DRONE_TAP", "action": "TOGGLE_VOICE_LISTENING"}))
            await asyncio.sleep(0.1)
            assert len(taps) == 1
    finally:
        await bridge.stop()
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

@pytest.mark.asyncio
async def test_bridge_async_tap_handler():
    port = get_free_port()
    bridge = DroneBridge(host="127.0.0.1", port=port)
    server_task = asyncio.create_task(bridge.start())
    await asyncio.sleep(0.1)

    async_taps = []
    async def async_handler():
        await asyncio.sleep(0.01)
        async_taps.append("async_ok")

    bridge.register_tap_handler(async_handler)

    try:
        async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
            await ws.send(json.dumps({"event": "DRONE_TAP"}))
            await asyncio.sleep(0.1)
            assert async_taps == ["async_ok"]
    finally:
        await bridge.stop()
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

@pytest.mark.asyncio
async def test_bridge_no_clients():
    port = get_free_port()
    bridge = DroneBridge(host="127.0.0.1", port=port)
    # Should safely return without error when no clients are connected
    await bridge.broadcast_state("idle")
    await bridge.broadcast_gesture("recoil")

@pytest.mark.asyncio
async def test_bridge_invalid_message():
    port = get_free_port()
    bridge = DroneBridge(host="127.0.0.1", port=port)
    server_task = asyncio.create_task(bridge.start())
    await asyncio.sleep(0.1)

    try:
        async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
            # Send non-JSON message - should be logged and not crash server
            await ws.send("non-json-payload")
            await asyncio.sleep(0.05)
            # Send non-tap JSON
            await ws.send(json.dumps({"event": "OTHER_EVENT"}))
            await asyncio.sleep(0.05)
    finally:
        await bridge.stop()
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

@pytest.mark.asyncio
async def test_bridge_jarvis_state_sync(tmp_path):
    port = get_free_port()
    state_file = tmp_path / "state.json"
    socket_path = tmp_path / "control.sock"

    # Start with initial state
    state_file.write_text(json.dumps({"state": "idle", "tools_in_flight": 0}))

    bridge = DroneBridge(
        host="127.0.0.1",
        port=port,
        enable_jarvis_sync=True,
        state_file=state_file,
        socket_path=socket_path
    )
    server_task = asyncio.create_task(bridge.start())
    await asyncio.sleep(0.1)

    try:
        async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
            # 1. Update state to listening
            state_file.write_text(json.dumps({"state": "listening", "listening": True, "tools_in_flight": 0}))
            msg_state = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            assert msg_state == {"version": "1.0", "type": "STATE", "state": "listening"}
            msg_gesture = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            assert msg_gesture == {"version": "1.0", "type": "GESTURE", "name": "nod"}

            # 2. Update state to thinking (with tools in flight)
            state_file.write_text(json.dumps({"state": "thinking", "tools_in_flight": 2}))
            msg_thinking = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            assert msg_thinking == {"version": "1.0", "type": "STATE", "state": "thinking"}

            # 3. Tool completed -> transitions to complete and triggers gyroRoll
            state_file.write_text(json.dumps({"state": "speaking", "tools_in_flight": 0}))
            msg_comp = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            assert msg_comp == {"version": "1.0", "type": "STATE", "state": "complete"}
            msg_roll = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            assert msg_roll == {"version": "1.0", "type": "GESTURE", "name": "gyroRoll"}
    finally:
        await bridge.stop()
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

@pytest.mark.asyncio
async def test_bridge_tap_triggers_jarvis_socket(tmp_path):
    port = get_free_port()
    socket_path = tmp_path / "control.sock"
    commands_received = []

    async def handle_unix_client(reader, writer):
        line = await reader.readline()
        cmd = line.decode().strip()
        commands_received.append(cmd)
        writer.write(b'{"muted": false, "status": "awake"}\n')
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    unix_server = await asyncio.start_unix_server(handle_unix_client, path=str(socket_path))

    bridge = DroneBridge(
        host="127.0.0.1",
        port=port,
        enable_jarvis_sync=True,
        socket_path=socket_path
    )
    server_task = asyncio.create_task(bridge.start())
    await asyncio.sleep(0.1)

    try:
        async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
            # Send DRONE_TAP from overlay
            await ws.send(json.dumps({"version": "1.0", "event": "DRONE_TAP"}))
            await asyncio.sleep(0.2)
            assert "listen toggle" in commands_received
    finally:
        await bridge.stop()
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass
        unix_server.close()
        await unix_server.wait_closed()

@pytest.mark.asyncio
async def test_bridge_broadcast_visibility():
    port = get_free_port()
    bridge = DroneBridge(host="127.0.0.1", port=port)
    server_task = asyncio.create_task(bridge.start())
    await asyncio.sleep(0.1)

    try:
        async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
            # Broadcast disappear
            await bridge.broadcast_visibility("disappear")
            msg1 = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            assert msg1 == {"version": "1.0", "type": "VISIBILITY", "action": "disappear"}

            # Broadcast appear
            await bridge.broadcast_visibility("appear")
            msg2 = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            assert msg2 == {"version": "1.0", "type": "VISIBILITY", "action": "appear"}

            # Broadcast toggle
            await bridge.broadcast_visibility("toggle")
            msg3 = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            assert msg3 == {"version": "1.0", "type": "VISIBILITY", "action": "toggle"}
    finally:
        await bridge.stop()
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

@pytest.mark.asyncio
async def test_bridge_relays_client_visibility_command():
    port = get_free_port()
    bridge = DroneBridge(host="127.0.0.1", port=port)
    server_task = asyncio.create_task(bridge.start())
    await asyncio.sleep(0.1)

    try:
        # Client 1: Drone overlay listener
        async with websockets.connect(f"ws://127.0.0.1:{port}") as overlay_ws:
            # Client 2: CLI sender sending disappear
            from shell.drone.bridge import _client_send
            await _client_send(port, {"version": "1.0", "type": "VISIBILITY", "action": "disappear"})

            # Overlay should receive the relayed visibility command
            msg = json.loads(await asyncio.wait_for(overlay_ws.recv(), timeout=1.5))
            assert msg == {"version": "1.0", "type": "VISIBILITY", "action": "disappear"}

            # Client 2: CLI sender sending appear
            await _client_send(port, {"version": "1.0", "type": "VISIBILITY", "action": "appear"})
            msg2 = json.loads(await asyncio.wait_for(overlay_ws.recv(), timeout=1.5))
            assert msg2 == {"version": "1.0", "type": "VISIBILITY", "action": "appear"}
    finally:
        await bridge.stop()
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

@pytest.mark.asyncio
async def test_unified_skills_drone_control(monkeypatch):
    from control.skills import UnifiedSkills
    import subprocess

    calls = []
    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        class DummyProc:
            returncode = 0
            stdout = "Sent 'disappear' visibility command to drone on port 8768"
        return DummyProc()

    monkeypatch.setattr(subprocess, "run", fake_run)
    skills = UnifiedSkills()

    # Check declaration exists
    drone_decl = next((d for d in skills.declarations if d.get("name") == "drone_control"), None)
    assert drone_decl is not None
    assert "action" in drone_decl["parameters_json_schema"]["properties"]

    # Execute disappear
    res = json.loads(await skills.execute("drone_control", {"action": "hide"}))
    assert res["ok"] is True
    assert res["action"] == "disappear"
    assert calls[-1][-1] == "disappear"

    # Execute appear
    res = json.loads(await skills.execute("drone_control", {"action": "show"}))
    assert res["ok"] is True
    assert res["action"] == "appear"
    assert calls[-1][-1] == "appear"

    # Execute toggle
    res = json.loads(await skills.execute("drone_control", {"action": "toggle"}))
    assert res["ok"] is True
    assert res["action"] == "toggle"
    assert calls[-1][-1] == "toggle"


def test_map_jarvis_state_filtering():
    import time
    bridge = DroneBridge()

    # 1. Benign / stale turn error should NOT trigger alert if state is idle
    stale_error_data = {
        "state": "idle",
        "error": "No spoken answer was received.",
        "connected": True,
        "tools_in_flight": 0
    }
    assert bridge._map_jarvis_state(stale_error_data) == "idle"

    # 2. Genuine raw_state error or alert triggers alert
    assert bridge._map_jarvis_state({"state": "alert"}) == "alert"
    assert bridge._map_jarvis_state({"state": "error"}) == "alert"

    # 3. Active recent critical alert within 6 seconds triggers alert
    active_alert_data = {
        "state": "idle",
        "recent_alerts": [
            {"priority": "critical", "timestamp": time.time() - 2, "text": "High temp"}
        ]
    }
    assert bridge._map_jarvis_state(active_alert_data) == "alert"

    # 4. Expired alert does not trigger alert
    expired_alert_data = {
        "state": "idle",
        "recent_alerts": [
            {"priority": "critical", "timestamp": time.time() - 10, "text": "Old alert"}
        ]
    }
    assert bridge._map_jarvis_state(expired_alert_data) == "idle"

    # 5. Normal states
    assert bridge._map_jarvis_state({"state": "speaking"}) == "speaking"
    assert bridge._map_jarvis_state({"state": "listening", "listening": True}) == "listening"
    assert bridge._map_jarvis_state({"state": "thinking", "tools_in_flight": 1}) == "thinking"


