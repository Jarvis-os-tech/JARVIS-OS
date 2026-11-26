"""Bounded offline recognition and exact short-command routing.

Audio stays in memory. A separate, single-request worker owns Whistle's
non-thread-safe native runtime; deadlines terminate it rather than leaving
inference running on the audio loop.
"""
from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import re
import sys
import time


@dataclass
class LocalSpeechConfig:
    enabled: bool = False
    max_command_seconds: float = 2.5
    decode_timeout: float = .5
    minimum_word_probability: float = .5
    offline_decode_timeout: float = 5.0
    needle_enabled: bool = False
    needle_timeout: float = 10.0
    needle_minimum_confidence: float = .8

    def validate(self):
        if type(self.needle_enabled) is not bool:
            raise ValueError('local_speech.needle_enabled must be a boolean')
        for name, low, high in (('needle_timeout', .1, 10), ('offline_decode_timeout', .1, 10), ('needle_minimum_confidence', .5, 1)):
            value = getattr(self, name)
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or not low <= value <= high):
                raise ValueError('Invalid Needle timeout or confidence threshold')
        if type(self.enabled) is not bool:
            raise ValueError('local_speech.enabled must be a boolean')
        for name, low, high in (('max_command_seconds', 1, 5),
                                ('decode_timeout', .05, 1),
                                ('minimum_word_probability', .5, 1)):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high:
                raise ValueError(f'local_speech.{name} must be between {low} and {high}')
        return self


def normalize(text):
    return re.sub(r'[^a-z0-9% ]', '', text.casefold()).strip()


def app_names(rows):
    """Only exact, unambiguous installed application names become commands."""
    aliases = {}
    for identity, description in rows:
        for name in (normalize(description.split(';')[0]), normalize(identity)):
            aliases.setdefault(name, set()).add(identity)
    return {name: next(iter(ids)) for name, ids in aliases.items() if len(ids) == 1 and name}


def command_for(text, apps):
    from control.command_values import number_slots, parse_control_command, protected_ranges
    if not isinstance(text, str) or protected_ranges(text):
        return None
    parsed = parse_control_command(text)
    if parsed:
        return parsed
    raw_clean = normalize(text.replace("'", ""))
    if re.search(
        r'\b(dont|do not|not|never|avoid|except|unless|if|why|explain|what|how|whether|and|then|or|phone|mobile|android|smartphone)\b',
        raw_clean,
    ):
        return None
    text = normalize(text)
    text = re.sub(r'^(?:(?:hey |okay |ok )?jarvis )', '', text)
    text = re.sub(r'^(?:can|could|would|will) you ', '', text)
    text = re.sub(r'^please ', '', text)
    text = re.sub(r' please$', '', text)
    if text in ('stop', 'stop talking', 'stop speaking', 'be quiet'):
        return ('stop', {})
    if text in ('standby', 'stand by', 'go to standby', 'go to sleep'):
        return ('enter_standby', {})
    if text in ('mute', 'mute audio', 'mute the audio', 'mute speakers'):
        return ('system_control', {'action': 'mute_set', 'enabled': True})
    if text in ('unmute', 'unmute audio', 'unmute the audio', 'unmute speakers'):
        return ('system_control', {'action': 'mute_set', 'enabled': False})
    for noun in ('volume', 'brightness'):
        if text in (f'{noun} up', f'increase {noun}', f'turn up the {noun}'):
            return ('system_control', {'action': noun + '_adjust', 'value': 5})
        if text in (f'{noun} down', f'decrease {noun}', f'turn down the {noun}'):
            return ('system_control', {'action': noun + '_adjust', 'value': -5})
    if (text in ('disappear', 'disapper', 'vanish')
            or text in ('disappear the drone', 'disappear drone', 'drone disappear',
                        'disapper the drone', 'disapper drone', 'drone disapper',
                        'hide the drone', 'hide drone', 'drone hide',
                        'close the drone', 'close drone', 'drone close',
                        'make the drone disappear', 'cloak the drone', 'cloak drone',
                        'dismiss the drone', 'dismiss drone', 'vanish the drone', 'drone vanish')
            or (re.search(r'\b(?:disappear|disapper|hide|cloak|vanish|dismiss)\b', text) and 'drone' in text)):
        return ('drone_control', {'action': 'disappear'})
    if (text in ('appear',)
            or text in ('appear the drone', 'appear drone', 'drone appear',
                        'show the drone', 'show drone', 'drone show',
                        'open the drone', 'open drone', 'drone open',
                        'make the drone appear', 'bring back the drone', 'bring the drone back',
                        'deploy the drone', 'deploy drone', 'uncloak the drone', 'uncloak drone')
            or (re.search(r'\b(?:appear|show|uncloak|deploy)\b', text) and 'drone' in text)):
        return ('drone_control', {'action': 'appear'})
    if text in ('toggle the drone', 'toggle drone', 'drone toggle') or (re.search(r'\btoggle\b', text) and 'drone' in text):
        return ('drone_control', {'action': 'toggle'})
    if text in ('lock screen', 'lock the screen', 'lock pc', 'lock the pc',
                'lock computer', 'lock the computer', 'lock session', 'lock my screen', 'screen lock'):
        return ('lock_screen', {})
    if text in ('take a screenshot', 'take screenshot', 'capture screenshot',
                'capture screen', 'capture the screen', 'screenshot', 'screenshot screen',
                'take a full screenshot', 'take full screenshot', 'take a fullscreen screenshot'):
        return ('take_screenshot', {'region': 'full'})
    if text in ('screenshot active window', 'screenshot the active window',
                'screenshot this window', 'screenshot window', 'screenshot the window',
                'take a screenshot of the window', 'take a screenshot of this window',
                'take a screenshot of the active window', 'capture active window',
                'capture this window', 'active window screenshot'):
        return ('take_screenshot', {'region': 'active'})
    if text in ('workspace back', 'previous workspace', 'prev workspace', 'last workspace',
                'go back a workspace', 'switch back a workspace', 'go to previous workspace',
                'go to the previous workspace', 'switch to previous workspace',
                'switch to the previous workspace', 'back to previous workspace',
                'back to last workspace', 'go back to previous workspace',
                'go back to the previous workspace'):
        return ('system_control', {'action': 'workspace_back'})
    move_ws = re.fullmatch(
        r'(?:move|send|put) (?:(?:the |this |that |active |current )?window|(?:this|that|it)) (?:to|on|onto) workspace (.+)',
        text,
    )
    if move_ws:
        fragment = move_ws[1].strip()
        try:
            slots = number_slots(fragment)
        except (ImportError, ValueError, NotImplementedError):
            slots = []
        if len(slots) == 1 and slots[0]['start'] == 0 and slots[0]['end'] == len(fragment):
            val = slots[0]['value']
            if val == int(val) and 1 <= int(val) <= 10:
                return ('move_window_to_workspace', {'workspace': int(val)})
    if text in ('close window', 'close the window', 'close this window', 'close that window',
                'close active window', 'close current window', 'close this', 'close that'):
        return ('system_control', {'action': 'window_close'})
    if text in ('fullscreen', 'full screen', 'toggle fullscreen', 'fullscreen window',
                'fullscreen the window', 'fullscreen this', 'fullscreen this window',
                'make this fullscreen', 'make window fullscreen', 'make the window fullscreen',
                'enter fullscreen', 'exit fullscreen'):
        return ('system_control', {'action': 'window_fullscreen'})
    if text in ('minimize', 'minimise', 'minimize window', 'minimise window',
                'minimize the window', 'minimise the window', 'minimize this',
                'minimize this window', 'minimize that window', 'minimize active window',
                'minimize current window'):
        return ('system_control', {'action': 'window_minimize'})
    if text in ('play', 'play music', 'play the music', 'play media', 'play audio',
                'resume music', 'resume the music', 'resume media', 'resume playback', 'resume audio'):
        return ('system_control', {'action': 'media_play'})
    if text in ('pause', 'pause music', 'pause the music', 'pause media', 'pause playback', 'pause audio', 'pause video'):
        return ('system_control', {'action': 'media_pause'})
    if text in ('play pause', 'toggle playback', 'toggle media', 'toggle music'):
        return ('system_control', {'action': 'media_play_pause'})
    if text in ('next track', 'next song', 'skip track', 'skip the track', 'skip song', 'skip the song',
                'next media', 'skip this song', 'skip this track', 'next'):
        return ('system_control', {'action': 'media_next'})
    if text in ('previous track', 'previous song', 'prev track', 'prev song',
                'last song', 'last track', 'previous media', 'go back a track', 'go back a song'):
        return ('system_control', {'action': 'media_previous'})
    audio_in = re.fullmatch(
        r'(?:switch|change|set) (?:the )?(?:mic|microphone|audio input|input)(?: device| source)? to (.+)',
        text,
    )
    if audio_in and audio_in[1].strip():
        return ('audio_set_device', {'device': audio_in[1].strip(), 'kind': 'input', 'move_streams': True})
    audio_out = re.fullmatch(
        r'(?:switch|change|set) (?:the )?(?:audio|sound|audio output|output|playback)(?: device| sink)? to (.+)',
        text,
    )
    if audio_out and audio_out[1].strip() and 'volume' not in audio_out[1]:
        return ('audio_set_device', {'device': audio_out[1].strip(), 'kind': 'output', 'move_streams': True})
    audio_out_short = re.fullmatch(
        r'switch (?:audio |sound )?to (?:the )?(.+? (?:speakers?|headphones?|headset|earbuds?|hdmi))',
        text,
    )
    if audio_out_short and audio_out_short[1].strip():
        return ('audio_set_device', {'device': audio_out_short[1].strip(), 'kind': 'output', 'move_streams': True})
    nav_match = re.fullmatch(r'(?:navigate to|go to|open|show) (?:the |my )?(downloads|documents|pictures|projects|videos|music|desktop)(?: folder| directory| section)?', text)
    if nav_match:
        return ('file_operation', {'action': 'navigate', 'path': nav_match[1].capitalize()})
    focus_match = (
        re.fullmatch(r'focus (?:on )?(?:the )?(.+?)(?: window)?', text)
        or re.fullmatch(r'(?:switch to|bring up|activate) (?:the )?(.+?) window', text)
    )
    if focus_match:
        target = focus_match[1].strip()
        if target and target not in ('this', 'that', 'it', 'workspace'):
            return ('system_control', {'action': 'window_focus', 'target': target})
    switch_app = re.fullmatch(r'(?:switch to|focus) (?:the )?(.+)', text)
    if switch_app and switch_app[1] in apps:
        return ('system_control', {'action': 'window_focus', 'target': switch_app[1]})
    match = re.fullmatch(r'(?:open|launch|start) (.+)', text)
    if match and match[1] in apps:
        return ('launch_app', {'app': apps[match[1]]})
    return None


def could_be_command(text):
    """Release conversational audio early; partial text never executes tools."""
    text = normalize(text)
    text = re.sub(r'^(?:(?:hey |okay |ok )?jarvis(?: |$))', '', text)
    text = re.sub(r'^(?:can|could|would|will) you(?: |$)', '', text)
    text = re.sub(r'^please(?: |$)', '', text)
    return bool(text and text.split()[0] in {
        'open', 'launch', 'start', 'volume', 'brightness', 'set', 'increase',
        'decrease', 'turn', 'switch', 'change', 'workspace', 'go', 'stop', 'be',
        'standby', 'stand', 'mute', 'unmute', 'navigate', 'previous', 'prev', 'last',
        'drone', 'disappear', 'disapper', 'appear', 'hide', 'show', 'cloak', 'uncloak',
        'deploy', 'dismiss', 'toggle', 'vanish', 'make', 'bring', 'close', 'fullscreen',
        'full', 'minimize', 'minimise', 'focus', 'activate', 'move', 'send', 'put',
        'take', 'capture', 'screenshot', 'lock', 'screen', 'play', 'pause', 'resume',
        'skip', 'next', 'audio', 'sound', 'media', 'music', 'window'})


class WhistleClient:
    def __init__(self, config):
        self.config = config
        self.process = None
        self.ready = False
        self.error = ''
        self.last_decode_ms = None
        # Seed vocabulary hints with core control targets and assistant name
        self.keywords = ['volume', 'brightness', 'workspace', 'Jarvis']
        self._lock = asyncio.Lock()

    async def start(self):
        async with self._lock:
            await self._start()

    async def _start(self):
        if not self.config.enabled:
            return
        root = Path(os.environ.get('JARVIS_WHISTLE_HOME', str(Path.home() / '.local/share/jarvis-runtime/whistle')))
        if not all((root / name).exists() for name in ('python/needle', 'whistle.cact', 'libneedle.so')):
            self.error = 'Whistle runtime is not installed'
            return
        env = dict(os.environ, PYTHONPATH=str(root / 'python'),
                   NEEDLE_WHISTLE_WEIGHTS=str(root / 'whistle.cact'),
                   NEEDLE3_LIB_PATH=str(root / 'libneedle.so'),
                   NEEDLE_TELEMETRY='0', DO_NOT_TRACK='1', HF_HUB_OFFLINE='1',
                   OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='1')
        try:
            self.process = await asyncio.create_subprocess_exec(
                sys.executable, str(Path(__file__).with_name('whistle_worker.py')),
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL, env=env, limit=262144)
            message = await asyncio.wait_for(self.process.stdout.readline(), 5)
            self.ready = json.loads(message).get('ready') is True
            if not self.ready:
                raise RuntimeError('Whistle did not become ready')
            self.error = ''
        except Exception as error:
            await self.close()
            self.error = type(error).__name__

    async def maintain(self):
        while True:
            await asyncio.sleep(30)
            if self.config.enabled and not self.ready:
                await self.start()

    async def transcribe_offline(self, pcm):
        return await self.transcribe(pcm, timeout=self.config.offline_decode_timeout)

    async def transcribe(self, pcm, *, timeout=None):
        if not self.ready or not pcm or len(pcm) > 32000 * self.config.max_command_seconds:
            return None
        async with self._lock:
            started = time.monotonic()
            try:
                # Transmit bounded PCM audio and vocabulary hints to the local speech worker
                request = json.dumps({'pcm': base64.b64encode(pcm).decode(),
                                      'keywords': self.keywords[:128]}).encode() + b'\n'
                async with asyncio.timeout(self.config.decode_timeout if timeout is None else timeout):
                    self.process.stdin.write(request)
                    await self.process.stdin.drain()
                    result = json.loads(await self.process.stdout.readline())
                self.last_decode_ms = round((time.monotonic() - started) * 1000)
                words = result.get('words') or []
                if (not words or any(float(word.get('probability', 0)) < self.config.minimum_word_probability
                                     for word in words)):
                    return None
                return result.get('text') or None
            except asyncio.CancelledError:
                await self.close()
                raise
            except Exception as error:
                await self.close()
                self.error = type(error).__name__
                return None

    async def close(self):
        self.ready = False
        process, self.process = self.process, None
        if process is not None:
            if process.returncode is None:
                process.kill()
            await process.wait()

