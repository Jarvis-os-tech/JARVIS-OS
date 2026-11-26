import json

import pytest

from jarvis_control.config import Config
from jarvis_control.skills import ControlSkills, UnifiedSkills
from voice_layer.daemon import build_instruction
from skills.skills import DesktopSkills


@pytest.mark.asyncio
async def test_voice_catalog_keeps_native_controls_and_specialist_discovery():
    control = ControlSkills(Config())
    desktop = DesktopSkills()
    skills = UnifiedSkills(control_skills=control, desktop_skills=desktop)
    try:
        names = {tool['name'] for tool in skills.live_declarations}
        all_names = {tool['name'] for tool in skills.declarations}
        assert len(skills.live_declarations) <= 50
        assert len(skills.live_declarations) == len(names)
        assert {
            'system_control', 'open_application', 'press_key', 'manage_window',
            'control_wifi', 'control_bluetooth', 'control_notifications', 'control_night_light',
            'take_screenshot', 'clipboard', 'move_path', 'trash_path', 'manage_app_stage',
            'audio_list_devices', 'audio_set_device', 'control_display', 'screen_record',
            'recent_files', 'enter_standby', 'open_input_bar', 'control_vision_mode',
            'parse_command_values', 'discover_domain_tools', 'execute_domain_tool',
        } <= names
        # Overlapping legacy aliases are deduplicated from live_declarations but still executable
        for legacy in ('launch_app', 'web_search', 'open_page', 'remember', 'send_shortcut',
                       'file_operation', 'read_clipboard', 'write_clipboard', 'set_volume',
                       'linkedin_draft_post', 'start_harness_check', 'call_hermes_api'):
            assert legacy not in names
            assert legacy in all_names
        assert len(skills.live_declarations) < len(skills.declarations)
        assert len(json.dumps(skills.live_declarations)) < len(json.dumps(skills.declarations)) * .65
        assert 'github_connection_status' in all_names
        result = await skills.execute('discover_domain_tools', {'domain': 'github'})
        assert any(item['name'] == 'github_connection_status' for item in json.loads(result)['tools'])
        prompt = build_instruction([{'function_declarations': skills.live_declarations}])
        assert 'SPECIALIST CAPABILITIES' in prompt
        assert 'Do not perform discovery for an already attached everyday control' in prompt
    finally:
        await skills.close_agent_jobs()
