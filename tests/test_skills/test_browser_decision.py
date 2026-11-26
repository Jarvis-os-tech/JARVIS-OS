from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, MagicMock

import pytest

from skills.browser_decision import BrowserDecisionLoop


def response(operation, target='0'):
    value = MagicMock()
    value.answers = {'operation': NS(choice=operation, confidence=.9),
                     'click_target': NS(choice=target, confidence=.8),
                     'type_target': NS(choice=target, confidence=.8)}
    return value


@pytest.mark.asyncio
async def test_loop_clicks_one_ref_then_reobserves_and_finishes():
    gui = MagicMock()
    gui.browser_snapshot = AsyncMock(side_effect=[
        {'outline': '- link "Next"', 'refs': {'a': {'ref': 'r1', 'role': 'link', 'name': 'Next'}}},
        {'outline': '- heading "Finished"', 'content_refs': [{'role': 'heading', 'name': 'Finished'}]},
    ])
    gui.browser_click = AsyncMock(return_value={'status': 'dispatched'})
    client = MagicMock()
    client.aio.decisions.create = AsyncMock(return_value=response('click'))
    result = await BrowserDecisionLoop(gui, client).run('target', 'tab', 'Reach Finished', max_steps=1, expected_heading='Finished')
    assert result['status'] == 'completed'
    assert result['verified'] is True
    gui.browser_click.assert_awaited_once_with('target', 'tab', 'r1')
    assert gui.browser_snapshot.await_count == 2


@pytest.mark.asyncio
async def test_sensitive_page_stops_before_model_or_driver():
    gui = MagicMock()
    gui.browser_snapshot = AsyncMock(return_value={'outline': '- heading "Review"',
        'content_refs': [{'role': 'heading', 'name': 'Payment details'}],
        'refs': {'a': {'ref': 'r1', 'role': 'button', 'name': 'Continue'}}})
    client = MagicMock()
    client.aio.decisions.create = AsyncMock()
    result = await BrowserDecisionLoop(gui, client).run('target', 'tab', 'Continue')
    assert result['status'] == 'handoff_required'
    client.aio.decisions.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_typing_uses_only_caller_payload_once():
    gui = MagicMock()
    gui.browser_snapshot = AsyncMock(side_effect=[
        {'outline': '- textbox "Prompt"', 'refs': [
            {'ref': 'button', 'role': 'button', 'name': 'Next'},
            {'ref': 'r1', 'role': 'textbox', 'name': 'Prompt'},
        ]},
        {'outline': '- link "Preview"', 'refs': [
            {'ref': 'r2', 'role': 'link', 'name': 'Preview'},
        ]},
        {'outline': '- heading "Draft ready"', 'refs': {'b': {'ref': 'r2', 'role': 'heading', 'name': 'Draft ready'}}},
    ])
    gui.browser_type = AsyncMock(return_value={'status': 'dispatched'})
    gui.browser_click = AsyncMock(return_value={'status': 'dispatched'})
    client = MagicMock()
    client.aio.decisions.create = AsyncMock(side_effect=[response('type'), response('click'), response('done')])
    result = await BrowserDecisionLoop(gui, client).run(
        'target', 'tab', 'Fill the prompt', 'approved Telugu prompt')
    assert result['status'] == 'stopped_unverified'
    gui.browser_type.assert_awaited_once_with(
        'target', 'tab', 'r1', 'approved Telugu prompt', replace=True)
    gui.browser_click.assert_awaited_once_with('target', 'tab', 'r2')
    assert '"previous_actions": [{"step": 1, "operation": "type"' in (
        client.aio.decisions.create.await_args_list[1].kwargs['input'])


@pytest.mark.asyncio
async def test_empty_page_never_reports_completed():
    gui = MagicMock()
    gui.browser_snapshot = AsyncMock(return_value={
        'refs': [], 'content_refs': [{'role': 'rootwebarea'}], 'outline': ''})
    client = MagicMock()
    client.aio.decisions.create = AsyncMock()
    result = await BrowserDecisionLoop(gui, client).run('target', 'tab', 'Continue')
    assert result['status'] == 'blocked'
    assert gui.browser_snapshot.await_count == 5
    client.aio.decisions.create.assert_not_awaited()
