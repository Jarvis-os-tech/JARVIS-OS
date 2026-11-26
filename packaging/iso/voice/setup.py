"""ISO-only spoken setup; the desktop voice subsystem is left unchanged."""
import asyncio
import contextlib
import json
import os
from pathlib import Path
import re
import subprocess

from google import genai
from google.genai import types
import sounddevice as sd
from websockets.asyncio.server import serve

BASE = Path(__file__).resolve().parent
SETTINGS = Path.home() / '.config/jarvis-voice'
ORIGIN = 'http://127.0.0.1:8878'
FIELDS = ('user_name', 'os_name', 'primary_focus', 'preferred_tone', 'language')
INSTRUCTION = """You are JARVIS, waking up for the first time. This is a voice-only
onboarding conversation. Speak briefly, naturally, and ask ONE question at a time.
Welcome the user, then ask their name. Wait for their spoken reply. Ask whether
they want to keep your name JARVIS or give you another name, without suggesting
example names. Then ask what they mainly do on this computer, then their preferred
speaking tone. Understand English and Telugu and respond in their chosen language.
Never ask them to type, select an option, press a mic, or click a button. Never
invent an answer. Clarify unclear answers by voice. Read back the collected profile
and ask for spoken confirmation. Only after they explicitly confirm, call
save_profile with all five fields and confirmed=true. After a successful save,
say a short welcome and tell them you are opening their desktop. Do not claim
success if the tool returns an error. You have no other tools or permissions."""
TOOL = {'function_declarations': [{
    'name': 'save_profile',
    'description': 'Save the profile only after the user explicitly confirms it aloud.',
    'parameters': {'type': 'OBJECT', 'properties': {
        **{key: {'type': 'STRING'} for key in FIELDS},
        'confirmed': {'type': 'BOOLEAN'},
    }, 'required': [*FIELDS, 'confirmed']},
}]}


def private_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix('.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as output:
        output.write(text)
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def profile_from(args):
    if args.get('confirmed') is not True:
        raise ValueError('Ask for spoken confirmation first.')
    profile = {}
    for key in FIELDS:
        value = args.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > 200:
            raise ValueError('Ask the user for a valid ' + key)
        profile[key] = value.strip()
    return {**profile, 'initialized': True, 'wake_word': profile['os_name'].lower(),
            'assistant': profile['os_name'], 'user': profile['user_name']}


async def conversation(ws, key):
    output = asyncio.Queue(maxsize=200)
    listening = False
    saved = False
    async def status(state, text=''):
        await ws.send(json.dumps({'state': state, 'text': text}))

    config = {'response_modalities': ['AUDIO'], 'system_instruction': INSTRUCTION,
              'speech_config': {'voice_config': {'prebuilt_voice_config': {'voice_name': 'Charon'}}},
              'input_audio_transcription': {}, 'output_audio_transcription': {},
              'tools': [TOOL]}
    async with genai.Client(api_key=key, http_options={'api_version': 'v1beta'}).aio as client:
        async with client.live.connect(model='gemini-3.8-live', config=config) as live:
            # A connected Live session, not a key-shaped string, unlocks setup.
            private_write(SETTINGS / 'env', 'GEMINI_API_KEY=' + key + '\n')
            await status('think', 'Connected. Starting your voice introduction…')
            with sd.RawInputStream(samplerate=16000, channels=1, dtype='int16', blocksize=320) as mic, \
                 sd.RawOutputStream(samplerate=24000, channels=1, dtype='int16') as speaker:
                async def capture():
                    while True:
                        data, overflow = await asyncio.to_thread(mic.read, 320)
                        if listening and not overflow:
                            await live.send_realtime_input(audio=types.Blob(data=bytes(data), mime_type='audio/pcm;rate=16000'))

                async def playback():
                    while True:
                        data = await output.get()
                        try:
                            await asyncio.to_thread(speaker.write, data)
                        finally:
                            output.task_done()

                async def receive():
                    nonlocal listening, saved
                    transcript = ''
                    while True:
                        async for response in live.receive():
                            content = response.server_content
                            if content:
                                if content.model_turn:
                                    listening = False
                                    for part in content.model_turn.parts or []:
                                        if part.inline_data and part.inline_data.data:
                                            await status('speak')
                                            await output.put(part.inline_data.data)
                                if content.output_transcription and content.output_transcription.text:
                                    transcript += content.output_transcription.text
                                    await status('speak', transcript)
                                if content.turn_complete:
                                    await output.join()
                                    # Let the output device drain before reopening capture.
                                    await asyncio.sleep(float(speaker.latency) + 0.15)
                                    if saved:
                                        await status('done', 'Welcome. Opening your desktop…')
                                        return
                                    listening = True
                                    await status('listen', 'Listening — reply aloud.')
                                    transcript = ''
                            if response.tool_call:
                                for call in response.tool_call.function_calls:
                                    try:
                                        if call.name != 'save_profile':
                                            raise ValueError('Unknown setup action')
                                        profile = profile_from(call.args)
                                        private_write(SETTINGS / 'profile.json', json.dumps(profile, indent=2))
                                        saved = True
                                        result = {'saved': True}
                                    except (ValueError, OSError) as error:
                                        result = {'error': str(error)}
                                    await live.send_tool_response(function_responses=[types.FunctionResponse(
                                        id=call.id, name=call.name, response=result)])

                tasks = [asyncio.create_task(capture()), asyncio.create_task(playback()),
                         asyncio.create_task(receive()), asyncio.create_task(ws.wait_closed())]
                try:
                    await live.send_realtime_input(text='Begin the welcome and ask my name. Wait for my spoken answer.')
                    done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                    for task in done:
                        task.result()
                    return saved and tasks[2] in done
                finally:
                    for task in tasks:
                        task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)


async def main():
    finished = asyncio.Event()
    active = False
    async def handler(ws):
        nonlocal active
        if active:
            await ws.close(1008, 'Setup already active')
            return
        active = True
        try:
            message = json.loads(await asyncio.wait_for(ws.recv(), 300))
            key = message.get('key', '').strip()
            if not re.fullmatch(r'AIza[\w-]{20,}', key):
                raise ValueError('Invalid key format')
            if await conversation(ws, key):
                finished.set()
        except Exception:
            # Provider exceptions can contain credentials; never send or log them.
            with contextlib.suppress(Exception):
                await ws.send(json.dumps({'state': 'error', 'text':
                    'Could not start or continue voice setup. Check your key, internet and microphone, then reconnect.'}))
        finally:
            active = False
            await ws.close()

    def request(connection, request):
        if request.headers.get('Host') != '127.0.0.1:8878':
            return connection.respond(403, 'Forbidden')
        if request.path == '/voice':
            return None
        if request.path != '/':
            return connection.respond(404, 'Not found')
        response = connection.respond(200, (BASE / 'welcome.html').read_text())
        del response.headers['Content-Type']
        response.headers['Content-Type'] = 'text/html; charset=utf-8'
        response.headers['Cache-Control'] = 'no-store'
        return response

    async with serve(handler, '127.0.0.1', 8878, origins=[ORIGIN],
                     process_request=request, max_size=4096):
        env = {**os.environ, 'LD_LIBRARY_PATH': str(BASE / 'browser-libs')}
        browser = subprocess.Popen([str(BASE / 'chromium/chromium'), '--ozone-platform=wayland',
            '--user-data-dir=' + str(SETTINGS / 'setup-browser'), '--no-first-run',
            '--password-store=basic', '--autoplay-policy=no-user-gesture-required', '--kiosk', ORIGIN], env=env)
        try:
            await finished.wait()
            subprocess.Popen(['qs', '-p', str(BASE / 'ui/Desktop.qml')])
        finally:
            browser.terminate()
            await asyncio.to_thread(browser.wait)
    os.execv(str(BASE / 'onboard'), [str(BASE / 'onboard')])


if __name__ == '__main__':
    os.umask(0o077)
    asyncio.run(main())
