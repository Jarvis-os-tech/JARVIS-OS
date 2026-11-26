import asyncio
import json
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest
from voice.local_speech import LocalSpeechConfig
from voice.needle_router import NeedleRouter, validate_prediction


def prediction(name, args, confidence=.95):
    return {'confidence': confidence, 'function_calls': [{'name': name, 'arguments': args}]}


@pytest.mark.parametrize('name,args,text,expected', [
    ('set_volume', {'value': 40}, 'please set the volume to forty', ('system_control', {'action':'volume_set','value':40})),
    ('change_volume', {'direction':'down'}, 'make the speakers quieter', ('system_control', {'action':'volume_adjust','value':-5})),
    ('change_brightness', {'direction':'up'}, 'make my screen brighter', ('system_control', {'action':'brightness_adjust','value':5})),
    ('open_application', {'app':'firefox'}, 'please open firefox for me', ('launch_app', {'app':'firefox'})),
    ('switch_workspace', {'workspace':2}, 'move me to workspace two', ('system_control', {'action':'workspace_switch','workspace':'2'})),
    ('workspace_back', {}, 'go back to previous workspace', ('system_control', {'action':'workspace_back'})),
    ('move_window_to_workspace', {'workspace': 3}, 'move this window to workspace three', ('move_window_to_workspace', {'workspace': 3})),
    ('close_window', {}, 'close this window', ('system_control', {'action': 'window_close'})),
    ('fullscreen_window', {}, 'make the window fullscreen', ('system_control', {'action': 'window_fullscreen'})),
    ('minimize_window', {}, 'minimize this window', ('system_control', {'action': 'window_minimize'})),
    ('focus_window', {'target': 'firefox'}, 'focus the firefox window', ('system_control', {'action': 'window_focus', 'target': 'firefox'})),
    ('take_screenshot', {'region': 'full'}, 'take a screenshot', ('take_screenshot', {'region': 'full'})),
    ('take_screenshot', {'region': 'active'}, 'capture active window screenshot', ('take_screenshot', {'region': 'active'})),
    ('lock_screen', {}, 'lock the screen', ('lock_screen', {})),
    ('media_play', {}, 'resume the music', ('system_control', {'action': 'media_play'})),
    ('media_pause', {}, 'pause the music', ('system_control', {'action': 'media_pause'})),
    ('media_next', {}, 'skip this track', ('system_control', {'action': 'media_next'})),
    ('media_previous', {}, 'go back to previous song', ('system_control', {'action': 'media_previous'})),
    ('switch_audio_device', {'device': 'headphones', 'kind': 'output'}, 'switch audio output to headphones', ('audio_set_device', {'device': 'headphones', 'kind': 'output', 'move_streams': True})),
    ('switch_audio_device', {'device': 'blue yeti', 'kind': 'input'}, 'switch microphone to blue yeti', ('audio_set_device', {'device': 'blue yeti', 'kind': 'input', 'move_streams': True})),
])
def test_grounded_offline_commands(name, args, text, expected):
    assert validate_prediction(prediction(name,args),text,{'firefox':'firefox'}) == expected


@pytest.mark.parametrize('name,args,text', [
    ('focus_window', {'target': 'terminal'}, 'focus firefox window'),
    ('switch_audio_device', {'device': 'speakers', 'kind': 'output'}, 'switch audio output to headphones'),
    ('switch_audio_device', {'device': 'blue yeti', 'kind': 'input'}, 'switch audio output to blue yeti'),
    ('media_play', {}, 'play bohemian rhapsody'),
    ('close_window', {}, 'close the drone'),
    ('lock_screen', {}, 'lock screen on my phone'),
    ('take_screenshot', {'region': 'active'}, 'take a full screenshot'),
])
def test_expanded_needle_commands_reject_ungrounded_targets(name, args, text):
    assert validate_prediction(prediction(name, args), text, {'firefox': 'firefox'}) is None


@pytest.mark.asyncio
async def test_local_lock_screen_preserves_confirmation_gate_when_online():
    from voice.config import Config
    from voice.daemon import LiveVoice
    from voice.playback import Playback

    voice = LiveVoice(
        Playback('test'),
        config=Config(),
        skills=NS(execute=AsyncMock(return_value={'status': 'needs_confirmation', 'action': 'lock_screen', 'confirmed': False})),
    )
    voice.connected = True
    voice._session = NS(send_client_content=AsyncMock())
    voice.gate.accepted_turns = 4
    voice.local_speech = NS(transcribe=AsyncMock(return_value='lock screen'))
    assert await voice._try_local_command(bytes(640), (4, 0))
    voice.skills.execute.assert_awaited_once_with('lock_screen', {})
    assert voice.last_local_outcome == 'needs_confirmation'
    assert voice._confirmation_gate_turn == 4
    voice._session.send_client_content.assert_awaited_once()
    sent_text = voice._session.send_client_content.call_args.kwargs['turns'][0].parts[0].text
    assert 'waiting for your confirmation' in sent_text
    assert 'Do not call tools' in sent_text


@pytest.mark.parametrize('text', ['do not open firefox', "don't open firefox", 'why open firefox',
                                   'explain how to open firefox', 'open firefox and delete documents',
                                   'if I open firefox', 'never open firefox'])
def test_negated_explanatory_or_multiple_actions_are_not_executed(text):
    assert validate_prediction(prediction('open_application', {'app':'firefox'}),text,{'firefox':'firefox'}) is None


@pytest.mark.parametrize('result,text', [
    (prediction('set_volume', {'value':70}), 'set volume 40'),
    (prediction('set_volume', {'value':140}), 'set volume 140'),
    (prediction('set_volume', {'value':True}), 'set volume one'),
    (prediction('change_volume', {'direction':'up'}), 'make the sound quieter'),
    (prediction('change_volume', {'direction':'down'}), 'lower the volume by ten'),
    (prediction('run_shell', {'command':'rm -rf ~'}), 'do a cleanup'),
    (prediction('open_application', {'app':'terminal'}), 'open firefox'),
    (prediction('set_volume', {'value':40}, .2), 'set volume 40'),
    (prediction('set_volume', {'value':40}, None), 'set volume 40'),
    (prediction('set_volume', {'value':40}, float('nan')), 'set volume 40'),
])
def test_unsafe_unconfident_and_ungrounded_predictions_are_rejected(result,text):
    assert validate_prediction(result,text,{'firefox':'firefox'}) is None


@pytest.mark.asyncio
async def test_timeout_stops_native_worker():
    config=LocalSpeechConfig(needle_enabled=True,needle_timeout=.05)
    router=NeedleRouter(config)
    killed=asyncio.Event()
    async def forever(): await asyncio.Event().wait()
    router.process=NS(stdin=NS(write=lambda data:None,drain=AsyncMock()),stdout=NS(readline=forever),
                      returncode=None,kill=killed.set,wait=AsyncMock())
    router.ready=True
    assert await router.route('make the sound quieter') is None
    assert killed.is_set()
    assert not router.ready


@pytest.mark.parametrize('name,text,expected', [
    ('decrease_volume', 'make the speakers quieter', ('system_control', {'action':'volume_adjust','value':-5})),
    ('increase_brightness', 'make the display brighter', ('system_control', {'action':'brightness_adjust','value':5})),
])
def test_single_action_schemas_still_require_grounded_direction(name,text,expected):
    assert validate_prediction(prediction(name,{}),text,{}) == expected


@pytest.mark.asyncio
async def test_needles_offline_prediction_uses_existing_executor_once():
    from voice.config import Config
    from voice.daemon import LiveVoice
    from voice.playback import Playback
    voice=LiveVoice(Playback('test'),config=Config(),skills=NS(execute=AsyncMock(return_value={'ok':True,'status':'completed'})))
    voice.local_speech=NS(transcribe=AsyncMock(return_value='make the speakers quieter'))
    voice.local_router=NS(config=LocalSpeechConfig(needle_enabled=True),ready=True,
                          route=AsyncMock(return_value=('system_control',{'action':'volume_adjust','value':-5})),
                          synthesize=AsyncMock(return_value=bytes(960)))
    assert await voice._try_local_command(bytes(640),(0,0))
    voice.skills.execute.assert_awaited_once_with('system_control',{'action':'volume_adjust','value':-5})
    voice.local_router.synthesize.assert_awaited_once_with('Volume decreased.')
    assert not voice._reply_authorized


@pytest.mark.asyncio
async def test_needle_does_not_delay_online_conversation():
    from voice.config import Config
    from voice.daemon import LiveVoice
    from voice.playback import Playback
    voice=LiveVoice(Playback('test'),config=Config())
    voice.connected=True
    voice.local_speech=NS(transcribe=AsyncMock(return_value='tell me about the weather'))
    voice.local_router=NS(config=LocalSpeechConfig(needle_enabled=True),route=AsyncMock())
    assert not await voice._try_local_command(bytes(640),(0,0))
    voice.local_router.route.assert_not_awaited()


def test_offline_feedback_never_claims_unverified_success():
    from control.outcomes import classify_result
    from voice.offline_speech import result_text
    text=result_text('system_control',{'action':'volume_set','value':40},classify_result({'ok':True,'status':'unverified'}))
    assert 'could not verify' in text
    assert 'set to' not in text


@pytest.mark.parametrize('text', ['is the screen brighter', 'are the speakers quieter',
                                   'could the screen be brighter', 'the volume is forty'])
def test_observations_and_questions_are_not_actions(text):
    assert validate_prediction(prediction('increase_brightness',{}),text,{}) is None


def test_compound_number_cannot_be_truncated_to_its_last_digit():
    assert validate_prediction(prediction('set_volume',{'value':1}), 'set volume to forty one',{}) is None
    assert validate_prediction(prediction('set_volume',{'value':41}), 'set volume to forty one',{}) == ('system_control',{'action':'volume_set','value':41})


@pytest.mark.asyncio
async def test_online_first_needle_executes_eligible_command_locally_without_cloud():
    from voice.config import Config
    from voice.daemon import LiveVoice
    from voice.playback import Playback

    voice = LiveVoice(Playback('test'), config=Config(),
                      skills=NS(execute=AsyncMock(return_value={'ok': True, 'status': 'completed'})))
    voice.connected = True
    voice.local_speech = NS(transcribe=AsyncMock(return_value='make the speakers quieter'))
    voice.local_router = NS(
        config=LocalSpeechConfig(needle_enabled=True),
        ready=True,
        route=AsyncMock(return_value=('system_control', {'action': 'volume_adjust', 'value': -5})),
        synthesize=AsyncMock(return_value=b''),
    )
    assert await voice._try_local_command(bytes(640), (0, 0))
    voice.local_router.route.assert_awaited_once_with('make the speakers quieter')
    voice.skills.execute.assert_awaited_once_with('system_control', {'action': 'volume_adjust', 'value': -5})
    assert voice.local_commands_executed == 1
    assert not voice._reply_authorized


@pytest.mark.asyncio
@pytest.mark.parametrize('text', [
    'do not make the speakers quieter',
    'set volume to "forty"',
    'set volume to forty on my phone',
])
async def test_online_needle_respects_negation_protected_ranges_and_phone_targets(text):
    from voice.config import Config
    from voice.daemon import LiveVoice
    from voice.playback import Playback

    voice = LiveVoice(Playback('test'), config=Config(),
                      skills=NS(execute=AsyncMock()))
    voice.connected = True
    voice.local_speech = NS(transcribe=AsyncMock(return_value=text))
    voice.local_router = NS(
        config=LocalSpeechConfig(needle_enabled=True),
        ready=True,
        route=AsyncMock(),
        synthesize=AsyncMock(return_value=b''),
    )
    assert not await voice._try_local_command(bytes(640), (0, 0))
    voice.local_router.route.assert_not_awaited()
    voice.skills.execute.assert_not_awaited()

