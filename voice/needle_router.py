"""Optional offline intent routing. Needle proposes one bounded local action only."""
from __future__ import annotations

import asyncio
import base64
import json
import math
import os
from pathlib import Path
import re
import sys

from .local_speech import normalize


def schemas(apps):
    def tool(name, description, properties):
        return {'name': name, 'description': description, 'parameters': {
            'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}}
    bounded = lambda low, high: {'type': 'integer', 'minimum': low, 'maximum': high}
    tools = [
        tool('set_volume', 'Set speaker volume to an explicitly requested percentage.', {'value': bounded(0, 100)}),
        tool('set_brightness', 'Set screen brightness to an explicitly requested percentage.', {'value': bounded(1, 100)}),
        tool('increase_volume', 'Make the speakers louder.', {}),
        tool('decrease_volume', 'Make the speakers quieter or softer.', {}),
        tool('increase_brightness', 'Make the screen brighter.', {}),
        tool('decrease_brightness', 'Make the screen dimmer.', {}),
        tool('switch_workspace', 'Switch to a numbered desktop workspace.', {'workspace': bounded(1, 10)}),
        tool('workspace_back', 'Switch back to the previous desktop workspace.', {}),
        tool('move_window_to_workspace', 'Move the active window to a numbered desktop workspace.', {'workspace': bounded(1, 10)}),
        tool('close_window', 'Close the active desktop window.', {}),
        tool('fullscreen_window', 'Toggle fullscreen on the active desktop window.', {}),
        tool('minimize_window', 'Minimize the active desktop window.', {}),
        tool('focus_window', 'Focus an open window or application by name.', {'target': {'type': 'string'}}),
        tool('take_screenshot', 'Capture a screenshot of the full screen or active window.',
             {'region': {'type': 'string', 'enum': ['full', 'active']}}),
        tool('lock_screen', 'Request locking the desktop screen session.', {}),
        tool('media_play', 'Start or resume media playback.', {}),
        tool('media_pause', 'Pause media playback.', {}),
        tool('media_next', 'Skip to the next media track.', {}),
        tool('media_previous', 'Return to the previous media track.', {}),
        tool('switch_audio_device', 'Switch the default audio output or input device.',
             {'device': {'type': 'string'}, 'kind': {'type': 'string', 'enum': ['output', 'input']}}),
    ]
    if apps:
        tools.append(tool('open_application', 'Open an installed app explicitly named by the user.',
                          {'app': {'type': 'string', 'enum': sorted(set(apps.values()))}}))
    return tools


def _numbers(text):
    ones = dict(zip('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split(), range(20)))
    tens = dict(zip('twenty thirty forty fifty sixty seventy eighty ninety'.split(), range(20, 100, 10)))
    tokens = re.findall(r'\d+|[a-z]+', text)
    values = {int(token) for token in tokens if token.isdigit()}
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token in tens:
            value = tens[token]
            if i+1 < len(tokens) and tokens[i+1] in ones and ones[tokens[i+1]] < 10:
                i += 1
                value += ones[tokens[i]]
            values.add(value)
        elif token in ones:
            if i+1 < len(tokens) and tokens[i+1] == 'hundred':
                values.add(ones[token] * 100)
                i += 1
            else:
                values.add(ones[token])
        elif token == 'hundred':
            values.add(100)
        i += 1
    return values


def eligible_text(text):
    from control.command_values import protected_ranges
    if not isinstance(text, str) or protected_ranges(text):
        return False
    text = normalize(text.replace("'", ''))
    if (not text or len(text) > 240 or re.search(
            r'\b(dont|do not|not|never|avoid|except|unless|if|why|explain|what|how|whether|and|then|or|phone|mobile|android|smartphone)\b',
            text)):
        return False
    text = re.sub(r'^(?:hey )?jarvis ', '', text)
    text = re.sub(r'^(?:can|could|would|will) you (?:please )?', '', text)
    text = re.sub(r'^i (?:want|need|would like) (?:you )?to ', '', text)
    text = re.sub(r'^please ', '', text)
    return bool(re.match(
        r'^(open|launch|start|close|focus|bring|activate|minimize|minimise|fullscreen|full|maximize|'
        r'make|turn|set|put|switch|change|use|go|move|send|increase|decrease|raise|lower|brighten|dim|'
        r'volume|brightness|workspace|take|capture|screenshot|lock|play|pause|resume|skip|next|previous|prev|'
        r'media|music|audio|sound|window|screen)\b',
        text,
    ))


def validate_prediction(result, text, apps, minimum_confidence=.8):
    """Model confidence never bypasses argument bounds, explicit targets or negation."""
    if not eligible_text(text):
        return None
    text = normalize(text.replace("'", ''))
    confidence = result.get('confidence')
    if (isinstance(confidence, bool) or not isinstance(confidence, (int, float))
            or not math.isfinite(confidence) or confidence < minimum_confidence or confidence > 1):
        return None
    calls = result.get('function_calls')
    if not isinstance(calls, list) or len(calls) != 1:
        return None
    call = calls[0]
    if not isinstance(call, dict):
        return None
    name, args = call.get('name'), call.get('arguments')
    if not isinstance(args, dict):
        return None
    if name in ('set_volume', 'set_brightness'):
        noun = 'volume' if name == 'set_volume' else 'brightness'
        value = args.get('value')
        if (set(args) != {'value'} or type(value) is not int or noun not in text
                or value not in _numbers(text) or not (0 if noun == 'volume' else 1) <= value <= 100):
            return None
        return 'system_control', {'action': noun + '_set', 'value': value}
    if name in ('increase_volume', 'decrease_volume', 'increase_brightness', 'decrease_brightness'):
        if args:
            return None
        direction = 'up' if name.startswith('increase') else 'down'
        name = 'change_volume' if name.endswith('volume') else 'change_brightness'
        args = {'direction': direction}
    if name in ('change_volume', 'change_brightness'):
        direction = args.get('direction')
        if set(args) != {'direction'} or direction not in ('up', 'down') or _numbers(text):
            return None
        noun = 'volume' if name == 'change_volume' else 'brightness'
        words = ({'up': r'louder|increase|raise|up', 'down': r'quieter|softer|decrease|lower|down'}
                 if noun == 'volume' else {'up': r'brighter|increase|raise|up', 'down': r'dimmer|decrease|lower|down'})
        if not re.search(r'\b(' + words[direction] + r')\b', text):
            return None
        target = (r'volume|sound|audio|speaker|louder|quieter|softer' if noun == 'volume'
                  else r'brightness|screen|display|brighter|dimmer')
        if not re.search(r'\b(' + target + r')\b', text):
            return None
        return 'system_control', {'action': noun + '_adjust', 'value': 5 if direction == 'up' else -5}
    if name == 'switch_workspace':
        value = args.get('workspace')
        if (set(args) == {'workspace'} and type(value) is int and 1 <= value <= 10
                and value in _numbers(text) and 'workspace' in text):
            return 'system_control', {'action': 'workspace_switch', 'workspace': str(value)}
    if name == 'workspace_back' and not args:
        if 'workspace' in text and re.search(r'\b(back|previous|prev|last)\b', text):
            return 'system_control', {'action': 'workspace_back'}
    if name == 'move_window_to_workspace':
        value = args.get('workspace')
        if (set(args) == {'workspace'} and type(value) is int and 1 <= value <= 10
                and value in _numbers(text) and 'workspace' in text
                and re.search(r'\b(move|send|put)\b', text)):
            return 'move_window_to_workspace', {'workspace': value}
    if name == 'close_window' and not args:
        if (re.search(r'\bclose\b', text)
                and re.search(r'\b(window|this|that|it|active|current)\b', text)
                and 'drone' not in text):
            return 'system_control', {'action': 'window_close'}
    if name == 'fullscreen_window' and not args:
        if re.search(r'\b(fullscreen|full screen|maximize)\b', text):
            return 'system_control', {'action': 'window_fullscreen'}
    if name == 'minimize_window' and not args:
        if re.search(r'\b(minimize|minimise)\b', text):
            return 'system_control', {'action': 'window_minimize'}
    if name == 'focus_window' and set(args) == {'target'} and isinstance(args['target'], str):
        target = normalize(args['target'])
        if (target and target not in ('this', 'that', 'it', 'workspace', 'standby', 'audio', 'speakers')
                and re.search(r'\b(focus|switch|bring|activate|window)\b', text)
                and re.search(r'\b' + re.escape(target) + r'\b', text)):
            return 'system_control', {'action': 'window_focus', 'target': args['target'].strip()}
    if name == 'take_screenshot' and set(args) == {'region'} and args['region'] in ('full', 'active'):
        if re.search(r'\b(screenshot|capture)\b', text):
            if args['region'] == 'active' and re.search(r'\b(window|active|this|current)\b', text):
                return 'take_screenshot', {'region': 'active'}
            if args['region'] == 'full' and (not re.search(r'\b(window|active)\b', text) or 'full' in text):
                return 'take_screenshot', {'region': 'full'}
    if name == 'lock_screen' and not args:
        if re.search(r'\block\b', text) and re.search(r'\b(screen|pc|computer|session)\b', text):
            return 'lock_screen', {}
    if name == 'media_play' and not args and not _numbers(text):
        stripped = re.sub(r'^(?:hey )?jarvis |^(?:can|could|would|will) you |^please | please$', '', text).strip()
        allowed_words = {'play', 'resume', 'the', 'my', 'music', 'media', 'playback', 'audio', 'song', 'track', 'video'}
        tokens = stripped.split()
        if tokens and re.search(r'\b(play|resume)\b', stripped) and set(tokens) <= allowed_words:
            return 'system_control', {'action': 'media_play'}
    if name == 'media_pause' and not args:
        if re.search(r'\bpause\b', text):
            return 'system_control', {'action': 'media_pause'}
    if name == 'media_next' and not args:
        if re.search(r'\b(next|skip)\b', text) and (
            re.search(r'\b(track|song|music|media|audio|video|this)\b', text) or text in ('next', 'skip')
        ):
            return 'system_control', {'action': 'media_next'}
    if name == 'media_previous' and not args:
        if re.search(r'\b(previous|prev|last|back)\b', text) and re.search(
            r'\b(track|song|music|media|audio|video)\b', text
        ):
            return 'system_control', {'action': 'media_previous'}
    if (name == 'switch_audio_device' and set(args) == {'device', 'kind'}
            and args['kind'] in ('output', 'input') and isinstance(args['device'], str)):
        dev = normalize(args['device'])
        if (dev and re.search(r'\b' + re.escape(dev) + r'\b', text)
                and re.search(r'\b(switch|change|set|use)\b', text)
                and re.search(r'\b(audio|sound|output|input|speaker|speakers|headphone|headphones|headset|earbuds|mic|microphone|device|sink|source|bluetooth|hdmi)\b', text)
                and (args['kind'] != 'input' or re.search(r'\b(mic|microphone|input|source)\b', text))):
            return 'audio_set_device', {'device': args['device'].strip(), 'kind': args['kind'], 'move_streams': True}
    if name == 'open_application' and set(args) == {'app'} and isinstance(args['app'], str):
        if not re.search(r'\b(open|launch|start)\b', text):
            return None
        for alias, identity in apps.items():
            if identity == args['app'] and re.search(r'\b' + re.escape(alias) + r'\b', text):
                return 'launch_app', {'app': identity}
    return None


class NeedleRouter:
    def __init__(self, config):
        self.config = config
        self.process = None
        self.ready = False
        self.error = ''
        self.last_inference_ms = None
        self.apps = {}
        self._lock = asyncio.Lock()

    async def start(self, apps):
        self.apps = dict(apps)
        if not self.config.needle_enabled:
            return
        root = Path(os.environ.get('JARVIS_NEEDLE_HOME', Path.home() / '.local/share/jarvis-runtime/needle'))
        if not all((root / name).exists() for name in ('python/needle', 'needle3.cact', 'libneedle.so')):
            self.error = 'Needle runtime is not installed'
            return
        env = dict(os.environ, PYTHONPATH=str(root / 'python'), JARVIS_NEEDLE_HOME=str(root),
                   NEEDLE3_LIB_PATH=str(root / 'libneedle.so'), NEEDLE_TELEMETRY='0', DO_NOT_TRACK='1',
                   HF_HUB_OFFLINE='1', OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='1')
        try:
            self.process = await asyncio.create_subprocess_exec(
                sys.executable, str(Path(__file__).with_name('needle_worker.py')),
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL, env=env, limit=1048576)
            self.process.stdin.write((json.dumps({'tools': schemas(apps)}) + '\n').encode())
            await self.process.stdin.drain()
            self.ready = json.loads(await asyncio.wait_for(self.process.stdout.readline(), 15)).get('ready') is True
            if not self.ready:
                raise RuntimeError('Needle initialization failed')
            self.error = ''
        except asyncio.CancelledError:
            await self.close()
            raise
        except Exception as error:
            await self.close()
            self.error = type(error).__name__

    async def route(self, text):
        if not self.ready or not text or not eligible_text(text):
            return None
        async with self._lock:
            try:
                async with asyncio.timeout(self.config.needle_timeout):
                    candidates = sorted({identity for alias, identity in self.apps.items()
                                         if re.search(r'\b' + re.escape(alias) + r'\b', normalize(text))})
                    self.process.stdin.write((json.dumps({'text': text, 'app_candidates': candidates}) + '\n').encode())
                    await self.process.stdin.drain()
                    result = json.loads(await self.process.stdout.readline())
                self.last_inference_ms = result.get('elapsed_ms')
                return validate_prediction(result, text, self.apps, self.config.needle_minimum_confidence)
            except asyncio.CancelledError:
                await self.close()
                raise
            except Exception as error:
                await self.close()
                self.error = type(error).__name__
                return None

    async def synthesize(self, text):
        if not self.ready:
            return None
        async with self._lock:
            try:
                async with asyncio.timeout(3):
                    self.process.stdin.write((json.dumps({'speak': text}) + '\n').encode())
                    await self.process.stdin.drain()
                    result = json.loads(await self.process.stdout.readline())
                pcm = base64.b64decode(result['pcm'], validate=True)
                return pcm if 0 < len(pcm) <= 48000 * 10 and len(pcm) % 2 == 0 else None
            except asyncio.CancelledError:
                await self.close()
                raise
            except Exception as error:
                await self.close()
                self.error = type(error).__name__
                return None

    async def maintain(self):
        while True:
            await asyncio.sleep(30)
            if self.config.needle_enabled and not self.ready:
                await self.start(self.apps)

    async def close(self):
        self.ready = False
        process, self.process = self.process, None
        if process is not None:
            if process.returncode is None:
                process.kill()
            await process.wait()
