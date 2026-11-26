import asyncio
import contextlib
import importlib.util
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace as N
import unittest
from unittest.mock import patch
from websockets.asyncio.client import connect
from websockets.exceptions import InvalidStatus

spec = importlib.util.spec_from_file_location('iso_voice_setup', Path(__file__).with_name('setup.py'))
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)

PROFILE = dict(user_name='Test User', os_name='Orion', primary_focus='Coding',
               preferred_tone='Concise', language='English', confirmed=True)

class SetupTests(unittest.TestCase):
    def test_requires_complete_spoken_confirmation(self):
        for args in ({}, {**PROFILE, 'confirmed': False}, {**PROFILE, 'user_name': ''}):
            with self.assertRaises(ValueError):
                setup.profile_from(args)
        self.assertEqual(setup.profile_from(PROFILE)['assistant'], 'Orion')

    def test_private_atomic_save(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'env'
            setup.private_write(path, 'first')
            setup.private_write(path, 'second')
            self.assertEqual(path.read_text(), 'second')
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertFalse(path.with_suffix('.tmp').exists())

    def test_only_key_can_be_typed(self):
        html = Path(__file__).with_name('welcome.html').read_text()
        self.assertEqual(html.count('<input '), 1)
        for forbidden in ('keyTest', 'id="reply"', 'id="chips"', 'id="send"', 'SpeechRecognition', 'localStorage'):
            self.assertNotIn(forbidden, html)
        self.assertIn('id="key" type="password"', html)

    def test_local_page_and_socket_boundary(self):
        async def check():
            with patch.object(setup.subprocess, 'Popen') as process:
                process.return_value.wait.return_value = 0
                server = asyncio.create_task(setup.main())
                try:
                    await asyncio.sleep(.1)
                    reader, writer = await asyncio.open_connection('127.0.0.1', 8878)
                    writer.write(b'GET / HTTP/1.1\r\nHost: 127.0.0.1:8878\r\nConnection: close\r\n\r\n')
                    await writer.drain()
                    page = await reader.read()
                    writer.close()
                    await writer.wait_closed()
                    self.assertIn(b'Content-Type: text/html; charset=utf-8', page)
                    self.assertNotIn(b'Content-Type: text/plain', page)
                    with self.assertRaises(InvalidStatus):
                        async with connect('ws://127.0.0.1:8878/voice', origin='http://untrusted.example'):
                            pass
                    async with connect('ws://127.0.0.1:8878/voice', origin=setup.ORIGIN) as ws:
                        await ws.send(json.dumps({'key': 'invalid'}))
                        self.assertEqual(json.loads(await ws.recv())['state'], 'error')
                finally:
                    server.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await server
        asyncio.run(check())

    def test_voice_turns_and_confirmed_profile(self):
        class Context:
            def __init__(self, value): self.value = value
            async def __aenter__(self): return self.value
            async def __aexit__(self, *args): pass
        class Stream:
            latency = 0
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, size):
                time.sleep(.02)
                return (b'\0' * (size * 2), False)
            def write(self, data): self.last_audio = data
        class Socket:
            messages = []
            async def send(self, data): self.messages.append(json.loads(data))
            async def wait_closed(self): await asyncio.Future()
        class Live:
            turns = 0
            mic_chunks = 0
            async def send_realtime_input(self, **kwargs):
                if 'audio' in kwargs: self.mic_chunks += 1
            async def send_tool_response(self, **kwargs): self.result = kwargs
            async def receive(self):
                self.turns += 1
                await asyncio.sleep(.03)
                content = N(model_turn=N(parts=[N(inline_data=N(data=b'\0' * 480))]),
                            output_transcription=N(text='Welcome'), turn_complete=True)
                if self.turns == 2:
                    yield N(server_content=None, tool_call=N(function_calls=[N(name='save_profile', id='1', args=PROFILE)]))
                yield N(server_content=content, tool_call=None)
        live = Live()
        client = N(live=N(connect=lambda **kwargs: Context(live)))
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(setup, 'SETTINGS', Path(directory)), \
             patch.object(setup.genai, 'Client', return_value=N(aio=Context(client))), \
             patch.object(setup.sd, 'RawInputStream', Stream), \
             patch.object(setup.sd, 'RawOutputStream', Stream):
            # Stream constructor accepts the same keyword arguments as sounddevice.
            Stream.__init__ = lambda self, **kwargs: None
            ws = Socket()
            self.assertTrue(asyncio.run(asyncio.wait_for(setup.conversation(ws, 'test-placeholder'), 3)))
            self.assertGreater(live.mic_chunks, 0)
            self.assertIn('listen', [m['state'] for m in ws.messages])
            self.assertEqual(ws.messages[-1]['state'], 'done')
            saved = json.loads((Path(directory) / 'profile.json').read_text())
            self.assertEqual(saved['user_name'], 'Test User')
            self.assertTrue(live.result['function_responses'][0].response['saved'])

if __name__ == '__main__':
    unittest.main()
