# tests/test_ipc.py
import asyncio
import json
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

@pytest.fixture
def socket_path(tmp_path):
    return tmp_path / 'test.sock'


def test_status_file_contains_a_freshness_timestamp(tmp_path, monkeypatch):
    from voice import config, ipc

    state_file = tmp_path / 'state.json'
    monkeypatch.setattr(config, 'STATE_FILE', state_file)
    monkeypatch.setattr(ipc.time, 'time', lambda: 1000)
    status = {'state': 'speaking'}
    ipc.ControlServer().broadcast_state(status)
    assert json.loads(state_file.read_text()) == {'state': 'speaking', 'status_written_at': 1000}
    assert status == {'state': 'speaking'}

@pytest.mark.asyncio
async def test_status_json(socket_path):
    from voice.ipc import ControlServer
    status = {'listening': True, 'connected': True, 'model': 'test'}
    server = ControlServer(socket_path=socket_path, status_provider=lambda: status)
    await server.start()
    try:
        reader, writer = await asyncio.open_unix_connection(str(socket_path))
        writer.write(b'status --json\n')
        await writer.drain()
        data = await asyncio.wait_for(reader.read(4096), 2)
        writer.close()
        result = json.loads(data.decode())
        assert result['listening'] is True
        assert result['model'] == 'test'
    finally:
        await server.close()

@pytest.mark.asyncio
async def test_listen_toggle(socket_path):
    from voice.ipc import ControlServer
    state = {'muted': False}
    def toggle():
        state['muted'] = not state['muted']
        return state['muted']
    server = ControlServer(
        socket_path=socket_path,
        status_provider=lambda: {'listening': not state['muted']},
        toggle_mute_cb=toggle,
    )
    await server.start()
    try:
        reader, writer = await asyncio.open_unix_connection(str(socket_path))
        writer.write(b'listen toggle\n')
        await writer.drain()
        data = await asyncio.wait_for(reader.read(4096), 2)
        writer.close()
        assert state['muted'] is True
        assert b'muted' in data.lower() or b'true' in data.lower()
    finally:
        await server.close()

@pytest.mark.asyncio
async def test_unknown_command(socket_path):
    from voice.ipc import ControlServer
    server = ControlServer(socket_path=socket_path, status_provider=lambda: {})
    await server.start()
    try:
        reader, writer = await asyncio.open_unix_connection(str(socket_path))
        writer.write(b'foobar\n')
        await writer.drain()
        data = await asyncio.wait_for(reader.read(4096), 2)
        writer.close()
        assert b'unknown' in data.lower() or b'error' in data.lower()
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_second_daemon_does_not_unlink_live_socket(socket_path):
    from voice.ipc import ControlServer
    first = ControlServer(socket_path=socket_path, status_provider=lambda: {'connected': True})
    second = ControlServer(socket_path=socket_path)
    await first.start()
    try:
        with pytest.raises(RuntimeError, match='already running'):
            await second.start()
        await second.close()
        assert socket_path.exists()
        reader, writer = await asyncio.open_unix_connection(str(socket_path))
        writer.write(b'status --json\n')
        await writer.drain()
        assert json.loads(await reader.readline())['connected']
        writer.close()
        await writer.wait_closed()
    finally:
        await first.close()


@pytest.mark.asyncio
async def test_control_path_never_replaces_regular_file(socket_path):
    from voice.ipc import ControlServer
    socket_path.write_text('keep this file')
    server = ControlServer(socket_path=socket_path)
    with pytest.raises(PermissionError):
        await server.start()
    await server.close()
    assert socket_path.read_text() == 'keep this file'


@pytest.mark.asyncio
async def test_standby_ipc_command(socket_path):
    from voice.ipc import ControlServer
    called = []
    server = ControlServer(
        socket_path=socket_path,
        standby_cb=lambda: called.append(True),
    )
    await server.start()
    try:
        reader, writer = await asyncio.open_unix_connection(str(socket_path))
        writer.write(b'standby\n')
        await writer.drain()
        data = await asyncio.wait_for(reader.read(4096), 2)
        writer.close()
        res = json.loads(data.decode())
        assert res.get('standby') is True
        assert res.get('status') == 'standby_requested'
        assert len(called) == 1
    finally:
        await server.close()



@pytest.mark.asyncio
async def test_local_confirm_and_cancel_await_control_callbacks():
    from unittest.mock import AsyncMock, Mock
    from voice.ipc import ControlServer
    confirm, cancel, interrupt = AsyncMock(return_value='confirmed'), AsyncMock(return_value='cancelled'), Mock()
    server = ControlServer(confirm_cb=confirm, cancel_cb=cancel, interrupt_cb=interrupt)
    assert json.loads(await server._dispatch('listen confirm')) == {'result': 'confirmed'}
    assert json.loads(await server._dispatch('listen cancel')) == {'result': 'cancelled'}
    confirm.assert_awaited_once()
    cancel.assert_awaited_once()
    interrupt.assert_called_once()


@pytest.mark.asyncio
async def test_socket_confirmation_returns_after_async_callback(tmp_path):
    from unittest.mock import AsyncMock
    from voice.ipc import ControlServer
    callback = AsyncMock(return_value='synthetic confirmed')
    server = ControlServer(socket_path=tmp_path / 'confirmation.sock', confirm_cb=callback)
    await server.start()
    try:
        reader, writer = await asyncio.open_unix_connection(str(server.socket_path))
        writer.write(b'listen confirm\n')
        await writer.drain()
        response = json.loads(await asyncio.wait_for(reader.readline(), 2))
        assert response == {'result': 'synthetic confirmed'}
        callback.assert_awaited_once()
        writer.close()
        await writer.wait_closed()
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_send_text_ipc_command(socket_path):
    from voice.ipc import ControlServer
    sent = []
    server = ControlServer(
        socket_path=socket_path,
        send_text_cb=lambda text: sent.append(text),
    )
    await server.start()
    try:
        reader, writer = await asyncio.open_unix_connection(str(socket_path))
        writer.write(b'send what is the weather\n')
        await writer.drain()
        data = await asyncio.wait_for(reader.read(4096), 2)
        writer.close()
        res = json.loads(data.decode())
        assert res.get('status') == 'sent'
        assert res.get('text') == 'what is the weather'
        assert sent == ['what is the weather']
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_wake_ipc_command(socket_path):
    from voice.ipc import ControlServer
    woken = []
    server = ControlServer(
        socket_path=socket_path,
        wake_cb=lambda: woken.append(True),
    )
    await server.start()
    try:
        reader, writer = await asyncio.open_unix_connection(str(socket_path))
        writer.write(b'wake\n')
        await writer.drain()
        data = await asyncio.wait_for(reader.read(4096), 2)
        writer.close()
        res = json.loads(data.decode())
        assert res.get('status') == 'awake'
        assert res.get('standby') is False
        assert woken == [True]
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_vision_mode_json_ipc_commands(socket_path):
    from voice.ipc import ControlServer
    current_mode = {'mode': 'off'}

    def set_mode(m):
        current_mode['mode'] = m
        return {'vision_mode': m}

    server = ControlServer(
        socket_path=socket_path,
        get_vision_mode_cb=lambda: current_mode['mode'],
        set_vision_mode_cb=set_mode,
    )
    await server.start()
    try:
        # 1. get_vision_mode when off
        reader, writer = await asyncio.open_unix_connection(str(socket_path))
        writer.write(json.dumps({'command': 'get_vision_mode'}).encode() + b'\n')
        await writer.drain()
        data = await asyncio.wait_for(reader.read(4096), 2)
        writer.close()
        res = json.loads(data.decode())
        assert res['status'] == 'ok'
        assert res['vision_mode'] == 'off'

        # 2. set_vision_mode to camera
        reader, writer = await asyncio.open_unix_connection(str(socket_path))
        writer.write(json.dumps({'command': 'set_vision_mode', 'mode': 'camera'}).encode() + b'\n')
        await writer.drain()
        data = await asyncio.wait_for(reader.read(4096), 2)
        writer.close()
        res = json.loads(data.decode())
        assert res['status'] == 'ok'
        assert res['vision_mode'] == 'camera'
        assert current_mode['mode'] == 'camera'

        # 3. get_vision_mode when camera
        reader, writer = await asyncio.open_unix_connection(str(socket_path))
        writer.write(json.dumps({'command': 'get_vision_mode'}).encode() + b'\n')
        await writer.drain()
        data = await asyncio.wait_for(reader.read(4096), 2)
        writer.close()
        res = json.loads(data.decode())
        assert res['status'] == 'ok'
        assert res['vision_mode'] == 'camera'

        # 4. text command: vision screen
        reader, writer = await asyncio.open_unix_connection(str(socket_path))
        writer.write(b'vision screen\n')
        await writer.drain()
        data = await asyncio.wait_for(reader.read(4096), 2)
        writer.close()
        res = json.loads(data.decode())
        assert res['status'] == 'ok'
        assert res['vision_mode'] == 'screen'
        assert current_mode['mode'] == 'screen'
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_sync_memory_command(socket_path):
    from voice.ipc import ControlServer
    recorded = []
    def record_cb(user, assistant):
        recorded.append((user, assistant))
        return True

    server = ControlServer(
        socket_path=socket_path,
        record_memory_cb=record_cb
    )
    await server.start()
    try:
        reader, writer = await asyncio.open_unix_connection(str(socket_path))
        cmd = {
            'command': 'sync_memory',
            'records': [
                {'role': 'user', 'content': 'Hello from phone'},
                {'role': 'model', 'content': 'Hello back on mobile'}
            ]
        }
        writer.write(json.dumps(cmd).encode() + b'\n')
        await writer.drain()
        data = await asyncio.wait_for(reader.read(4096), 2)
        writer.close()
        res = json.loads(data.decode())
        assert res['status'] == 'ok'
        assert res['saved'] is True
        assert len(recorded) == 1
        assert recorded[0] == ('Hello from phone', 'Hello back on mobile')
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_standby_toggle_uses_controller_atomically():
    from voice.ipc import ControlServer
    from voice.standby import StandbyController
    controller=StandbyController(detector=object())
    server=ControlServer(standby_toggle_cb=controller.toggle)
    first=json.loads(await server._handle_json_command({'command':'standby_toggle'}))
    second=json.loads(await server._dispatch('standby toggle'))
    assert first['standby'] is True and second['standby'] is False
    assert not controller.engaged


@pytest.mark.asyncio
async def test_ipc_multimodal_send_input(socket_path, tmp_path):
    from voice.ipc import ControlServer
    received_items = []
    def on_input(item):
        received_items.append(item)

    server = ControlServer(socket_path=socket_path, send_input_cb=on_input)
    await server.start()
    try:
        sample_img = tmp_path / "screenshot.png"
        sample_img.write_bytes(b"\x89PNG\r\n\x1a\nfakeimagebytes")

        reader, writer = await asyncio.open_unix_connection(str(socket_path))
        # 1. Test JSON send_input with file_path
        payload = {
            "command": "send_input",
            "text": "Analyze this screenshot",
            "file_path": str(sample_img)
        }
        writer.write(json.dumps(payload).encode() + b'\n')
        await writer.drain()
        data = await asyncio.wait_for(reader.read(4096), 2)
        res = json.loads(data.decode())
        assert res["status"] == "ok"
        assert res["queued"] is True
        assert res["name"] == "screenshot.png"
        assert len(received_items) == 1
        assert received_items[0]["text"] == "Analyze this screenshot"
        assert received_items[0]["data"] == b"\x89PNG\r\n\x1a\nfakeimagebytes"

        writer.close()
        await writer.wait_closed()

        # 2. Test line dispatch with --file
        reader2, writer2 = await asyncio.open_unix_connection(str(socket_path))
        writer2.write(f'send --file {sample_img} What is this?\n'.encode())
        await writer2.drain()
        data2 = await asyncio.wait_for(reader2.read(4096), 2)
        writer2.close()
        await writer2.wait_closed()
        res2 = json.loads(data2.decode())
        assert res2["status"] == "sent"
        assert res2["text"] == "What is this?"
        assert len(received_items) == 2
        assert received_items[1]["data"] == b"\x89PNG\r\n\x1a\nfakeimagebytes"
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_ipc_send_input_returns_error_when_cannot_queue(tmp_path):
    from voice.ipc import ControlServer

    text_calls = []
    server = ControlServer(send_text_cb=lambda t: text_calls.append(t))

    sample_file = tmp_path / "note.txt"
    sample_file.write_text("hello")

    # File input with send_input_cb=None must return an error, not {'status': 'ok', 'queued': False}
    for cmd in ('send_input', 'submit_input', 'attach', 'send_file'):
        res = json.loads(await server._handle_json_command({
            'command': cmd,
            'text': 'check this',
            'file_path': str(sample_file),
        }))
        assert res['status'] == 'error'
        assert 'error' in res
        assert res['queued'] is False
    assert text_calls == []

    # Line dispatch --file without send_input_cb must return an error instead of dropping the file
    line_res = json.loads(server._dispatch(f'send --file {sample_file} check this'))
    assert 'error' in line_res
    assert text_calls == []

    # Text-only send_input with both callbacks None must also return an error
    no_cb_server = ControlServer()
    res_no_cb = json.loads(await no_cb_server._handle_json_command({
        'command': 'send_input',
        'text': 'hello',
    }))
    assert res_no_cb['status'] == 'error'
    assert 'error' in res_no_cb
    assert res_no_cb['queued'] is False


@pytest.mark.asyncio
async def test_dictation_ipc_text_and_json_commands(socket_path):
    from voice.ipc import ControlServer

    state = {'active': False}
    calls = []

    async def on_dictation(action):
        calls.append(action)
        if action == 'start':
            state['active'] = True
        elif action in ('stop', 'cancel'):
            state['active'] = False
        elif action == 'toggle':
            state['active'] = not state['active']
        return {'active': state['active'], 'mode': 'dictation' if state['active'] else 'conversation'}

    server = ControlServer(
        socket_path=socket_path,
        status_provider=lambda: {
            'state': 'listening',
            'model': 'gemini-3.8-live',
            'mode': 'dictation' if state['active'] else 'conversation',
            'dictation': {'active': state['active']},
        },
        dictation_cb=on_dictation,
    )
    await server.start()
    try:
        for payload, expected_active in [
            (b'listen dictation start\n', True),
            (b'listen dictation status\n', True),
            ((json.dumps({'command': 'dictation', 'action': 'stop'}) + '\n').encode(), False),
            (b'dictate toggle\n', True),
            ((json.dumps({'command': 'dictation_cancel'}) + '\n').encode(), False),
        ]:
            reader, writer = await asyncio.open_unix_connection(str(socket_path))
            writer.write(payload)
            await writer.drain()
            res = json.loads((await asyncio.wait_for(reader.readline(), 2)).decode())
            writer.close()
            await writer.wait_closed()
            assert res['status'] == 'ok'
            assert res['active'] is expected_active

        # Human-readable status reports mode=dictation while active
        await on_dictation('start')
        assert 'mode=dictation' in server._dispatch('status')
        assert calls == ['start', 'status', 'stop', 'toggle', 'cancel', 'start']
    finally:
        await server.close()


def test_cli_listen_dictation_and_toggle_script(tmp_path, monkeypatch):
    import os
    import socket as pysocket
    import subprocess
    from voice import __main__ as cli, config as voice_config

    sent_cmds = []
    sock_file = tmp_path / 'control.sock'
    sock_file.touch()
    monkeypatch.setattr(voice_config, 'SOCKET_PATH', sock_file)

    class FakeSocket:
        def __init__(self, *a, **kw):
            pass

        def settimeout(self, t):
            pass

        def connect(self, path):
            pass

        def sendall(self, data):
            sent_cmds.append(data.decode().strip())

        def recv(self, n):
            return b'{"status":"ok","active":true}'

        def close(self):
            pass

    monkeypatch.setattr(pysocket, 'socket', FakeSocket)
    assert cli.main(['listen', 'dictation', 'start']) == 0
    assert cli.main(['dictate', 'stop']) == 0
    assert sent_cmds == ['listen dictation start', 'dictation stop']

    # Verify bin/jarvis-voice-toggle handles dictation toggle against a stub jarvis binary
    fake_bin = tmp_path / 'bin'
    fake_bin.mkdir()
    stub = fake_bin / 'jarvis'
    stub.write_text('#!/usr/bin/env bash\necho "{\\"status\\":\\"ok\\",\\"active\\":true}" "$@"\n')
    stub.chmod(0o755)
    toggle_copy = fake_bin / 'jarvis-voice-toggle'
    toggle_src = Path(__file__).resolve().parents[1] / 'bin' / 'jarvis-voice-toggle'
    toggle_copy.write_text(toggle_src.read_text())
    toggle_copy.chmod(0o755)
    proc = subprocess.run([str(toggle_copy), 'dictation', 'start'], capture_output=True, text=True, check=True)
    assert 'listen dictation start' in proc.stdout

    # Daemon down / empty status must not emit listening earcon or notify omarchy-shell listening
    events = fake_bin / 'events.log'
    shell_stub = fake_bin / 'omarchy-shell'
    shell_stub.write_text(f'#!/usr/bin/env bash\necho "shell:$*" >> "{events}"\n')
    shell_stub.chmod(0o755)
    stub.write_text('#!/usr/bin/env bash\nexit 1\n')
    env = dict(os.environ, PATH=f'{fake_bin}:{os.environ["PATH"]}')
    proc_down = subprocess.run([str(toggle_copy), 'toggle'], capture_output=True, text=True, env=env, check=True)
    assert proc_down.stdout.strip() == ''
    assert not events.exists()

    stub.write_text('#!/usr/bin/env bash\necho \'{"status": "ok", "muted": false}\'\n')
    proc_up = subprocess.run([str(toggle_copy), 'toggle'], capture_output=True, text=True, env=env, check=True)
    assert '"muted": false' in proc_up.stdout
    assert 'shell:-q dynamic-island voice listening' in events.read_text()

