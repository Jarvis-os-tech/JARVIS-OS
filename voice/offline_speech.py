"""Small offline voice module (offline fallback voice disabled)."""


class OfflineSpeech:
    """Offline synthetic voice disabled per user policy."""
    def __init__(self):
        self.sample_rate = 24000

    def synthesize(self, text):
        """Offline fallback speech disabled completely; returns empty audio."""
        return b''


def result_text(name, arguments, outcome):
    if outcome.status == 'needs_confirmation':
        return 'That action requires confirmation. Say confirm or cancel.'
    if not outcome.completed:
        return 'I could not verify that the local command completed.'
    if name == 'file_operation' and arguments.get('action') == 'navigate':
        return f"Opened {arguments.get('path')}."
    if name == 'launch_app':
        return 'The requested application is open.'
    if name == 'take_screenshot':
        return 'Screenshot captured.'
    if name == 'lock_screen':
        return 'Screen locked.'
    if name == 'move_window_to_workspace':
        return f"Moved window to workspace {arguments.get('workspace')}."
    if name == 'audio_set_device':
        return f"Switched audio {arguments.get('kind', 'output')} to {arguments.get('device')}."
    if name == 'system_control':
        action = arguments.get('action', '')
        if action in ('volume_set', 'brightness_set'):
            return f"{action.split('_')[0].capitalize()} set to {arguments['value']} percent."
        if action in ('volume_adjust', 'brightness_adjust'):
            direction = 'increased' if arguments['value'] > 0 else 'decreased'
            return f"{action.split('_')[0].capitalize()} {direction}."
        if action == 'workspace_switch':
            return f"Switched to workspace {arguments['workspace']}."
        if action == 'workspace_back':
            return 'Switched to previous workspace.'
        if action == 'window_close':
            return 'Window closed.'
        if action == 'window_fullscreen':
            return 'Toggled fullscreen.'
        if action == 'window_minimize':
            return 'Window minimized.'
        if action == 'window_focus':
            return f"Focused {arguments.get('target', 'window')}."
        if action == 'media_play':
            return 'Playback resumed.'
        if action == 'media_pause':
            return 'Playback paused.'
        if action == 'media_play_pause':
            return 'Playback toggled.'
        if action == 'media_next':
            return 'Skipped to next track.'
        if action == 'media_previous':
            return 'Returned to previous track.'
        if action == 'mute_set':
            return 'Speakers muted.' if arguments['enabled'] else 'Speakers unmuted.'
    return 'The local command completed.'
