"""Bounded, cancellable Carbon streaming with public summaries and real usage only."""
from __future__ import annotations

import asyncio
from contextvars import ContextVar
import json
import os
import time

from google import genai
from google.genai import types

from .cad_schema import provider_schema
from .config import api_key
from .projects import WorkspaceError

request_context = ContextVar('cad_model_request', default={})


def setting(name, default, low, high):
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        raise WorkspaceError(f'{name} must be a whole number.') from None
    if not low <= value <= high:
        raise WorkspaceError(f'{name} must be between {low} and {high}.')
    return value


def timeout_seconds():
    return setting('GEMINI_CAD_TIMEOUT_SECONDS', 900, 60, 3600)


def get(value, key, default=None):
    return value.get(key, default) if isinstance(value, dict) else getattr(value, key, default)


def usage_counts(usage):
    fields = {'input': 'total_input_tokens', 'output': 'total_output_tokens',
              'thinking': 'total_thought_tokens', 'tools': 'total_tool_use_tokens', 'total': 'total_tokens'}
    return {name: value for name, field in fields.items()
            if type(value := get(usage, field)) is int and value >= 0}


def request_error(error):
    if isinstance(error, WorkspaceError):
        return str(error)
    if 'timeout' in type(error).__name__.lower():
        return 'The connection to Carbon timed out before the response finished. Your plan and saved models are intact. Retry CAD when ready.'
    code = get(error, 'status_code') or get(error, 'code')
    return {401: 'The CAD API key was not accepted.', 403: 'Enable access and billing for Gemini Carbon on this API key.',
            404: 'The configured CAD model is unavailable. Check GEMINI_CAD_MODEL and account access.',
            429: 'Gemini CAD quota was reached. Retry when quota is available.',
            504: 'Carbon’s service timed out before completing this request. Your plan is saved. Retry CAD when ready.'}.get(
                code, f'Carbon could not finish this request ({type(error).__name__}). Your plan and saved models are intact.')


class StreamResult:
    """Allowlist event content: never retain signatures, raw thought data or tool arguments."""
    def __init__(self, observer):
        self.observer = observer
        self.text = ''
        self.summaries = {}
        self.usage = {}
        self.completed = False
        self.last_emit = 0
        self.phase = 'connecting'
        self.events = 0
        self.dirty = False

    def emit(self, force=False):
        if not self.dirty or (not force and time.monotonic() - self.last_emit < 1):
            return
        self.observer({'phase': self.phase, 'summary': '\n\n'.join(self.summaries.values())[-6000:],
                       'usage': self.usage, 'output_characters': len(self.text), 'events': self.events})
        self.last_emit = time.monotonic()
        self.dirty = False

    def add_summary(self, index, content):
        if get(content, 'type') == 'text' and isinstance(value := get(content, 'text'), str):
            if index in self.summaries or len(self.summaries) < 20:
                self.summaries[index] = (self.summaries.get(index, '') + value)[-2000:]
                self.dirty = True

    def feed(self, event):
        kind, index = get(event, 'event_type'), get(event, 'index', 0)
        self.events += 1
        if kind == 'interaction.created':
            self.phase = 'connected'; self.dirty = True
        elif kind == 'step.start':
            step = get(event, 'step'); step_type = get(step, 'type')
            if step_type in {'thought', 'model_output'}:
                self.phase = 'thinking' if step_type == 'thought' else 'responding'; self.dirty = True
                if step_type == 'thought':
                    for content in get(step, 'summary', []) or []:
                        self.add_summary(index, content)
            elif step_type == 'function_call' or (isinstance(step_type, str) and step_type.endswith('_call')):
                self.observer({'model_tool': str(get(step, 'name') or step_type)[:100]})
                raise WorkspaceError('Carbon requested a model-side tool, but this CAD workflow has none enabled. No requested tool was executed.')
        elif kind == 'step.delta':
            delta = get(event, 'delta')
            if get(delta, 'type') == 'thought_summary':
                self.add_summary(index, get(delta, 'content'))
            elif get(delta, 'type') == 'text' and isinstance(value := get(delta, 'text'), str):
                self.text += value; self.phase = 'responding'; self.dirty = True
                if len(self.text) > 500000:
                    raise WorkspaceError('Carbon’s response exceeded the CAD size limit. Simplify the design and retry.')
        elif kind == 'interaction.completed':
            interaction = get(event, 'interaction')
            self.usage.update(usage_counts(get(interaction, 'usage')))
            self.phase = 'received'; self.dirty = True; self.emit(True)
            if get(interaction, 'status') != 'completed':
                raise WorkspaceError('Carbon stopped before finishing its response, possibly at the token limit. No incomplete design was built. Simplify the request or retry.')
            self.completed = True
        elif kind == 'error':
            code = get(get(event, 'error'), 'code', '')
            if 'timeout' in str(code) or 'deadline' in str(code):
                raise WorkspaceError('Carbon’s service timed out before finishing. Your plan and saved models are intact. Retry CAD when ready.')
            raise WorkspaceError('Carbon reported a streaming error. Your plan and saved models are intact. Retry CAD when ready.')
        elif kind == 'step.stop':
            self.usage.update(usage_counts(get(event, 'usage')))
            self.dirty = True
        self.emit(kind in {'interaction.created', 'step.stop'})


async def stream_request(contract, instruction, data, selected_model, key, seconds, observer, cancelled):
    collector = StreamResult(observer)
    async def consume():
        async with genai.Client(api_key=key, http_options=types.HttpOptions(timeout=seconds * 1000,
                retry_options=types.HttpRetryOptions(attempts=1))).aio as client:
            stream = await client.interactions.create(model=selected_model, store=False, stream=True,
                input=instruction + '\nREFERENCE DATA:\n' + json.dumps(data, ensure_ascii=False),
                response_format={'type': 'text', 'mime_type': 'application/json',
                                 'schema': provider_schema(contract.model_json_schema())},
                generation_config={'thinking_level': 'high', 'thinking_summaries': 'auto',
                                   'max_output_tokens': 65536})
            async with stream:
                async for event in stream:
                    collector.feed(event)
            if not collector.completed:
                raise WorkspaceError('Carbon’s response stream ended before completion. Your plan is saved. Retry CAD when ready.')
            return contract.model_validate_json(collector.text)
    async def watch_cancel():
        while not cancelled():
            await asyncio.sleep(.25)
    if cancelled():
        raise WorkspaceError('CAD generation was cancelled.')
    task, watcher = asyncio.create_task(consume()), asyncio.create_task(watch_cancel())
    try:
        done, _ = await asyncio.wait({task, watcher}, timeout=seconds, return_when=asyncio.FIRST_COMPLETED)
        if watcher in done:
            raise WorkspaceError('CAD generation was cancelled.')
        if task not in done:
            limit = f'{seconds / 60:g} minutes' if seconds >= 60 else f'{seconds:g} seconds'
            raise WorkspaceError(f'Carbon did not finish this request within {limit}. Your plan and saved models are intact. Retry CAD when ready.')
        return await task
    finally:
        for pending in (task, watcher):
            if not pending.done():
                pending.cancel()
        await asyncio.gather(task, watcher, return_exceptions=True)
        collector.emit(True)


def request_model(contract, instruction, data, selected_model):
    key = os.getenv('GEMINI_CAD_API_KEY', '').strip() or api_key()
    if not key:
        raise WorkspaceError('Add a Gemini API key to enable CAD design.')
    context = request_context.get()
    try:
        return asyncio.run(stream_request(contract, instruction, data, selected_model, key, timeout_seconds(),
                                         context.get('observer', lambda _: None), context.get('cancelled', lambda: False)))
    except Exception as error:
        raise WorkspaceError(request_error(error)) from error
