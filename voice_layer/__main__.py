"""CLI entry point: python -m voice_layer"""
import argparse
import importlib.util
import os
import shutil
import subprocess
import sys


def _systemd_command(action: str) -> int:
    """Manage the jarvis-voice systemd user service."""
    service = 'jarvis-voice.service'
    if action == 'restart':
        print('Restarting JARVIS...')
        rc = subprocess.call(['systemctl', '--user', 'restart', service])
        if rc == 0:
            print('JARVIS is active and running.')
        return rc
    elif action in ('disable', 'disanble'):
        print('Disabling JARVIS service...')
        rc = subprocess.call(['systemctl', '--user', 'disable', '--now', service])
        if rc == 0:
            print('JARVIS service disabled and stopped.')
        return rc
    elif action == 'enable':
        print('Enabling JARVIS service...')
        rc = subprocess.call(['systemctl', '--user', 'enable', '--now', service])
        if rc == 0:
            print('JARVIS service enabled and active.')
        return rc
    elif action == 'start':
        print('Starting JARVIS...')
        return subprocess.call(['systemctl', '--user', 'start', service])
    elif action == 'stop':
        print('Stopping JARVIS...')
        return subprocess.call(['systemctl', '--user', 'stop', service])
    return 1


def _ipc_command(args):
    """Send a command to the running daemon via its control socket."""
    import socket
    from .config import SOCKET_PATH

    if not SOCKET_PATH.exists():
        print('jarvis-voice is not running', file=sys.stderr)
        return 1

    if args.command == 'status':
        cmd = 'status --json' if args.json else 'status'
    elif args.command == 'listen':
        action = args.action or 'toggle'
        if action in ('dictate', 'dictation'):
            sub = args.text_args[0] if getattr(args, 'text_args', None) else 'toggle'
            cmd = f'listen dictation {sub}'
        else:
            cmd = f'listen {action}'
    elif args.command in ('dictate', 'dictation'):
        sub = args.action or 'toggle'
        cmd = f'dictation {sub}'
    elif args.command == 'standby':
        cmd = 'wake' if args.action == 'off' else 'standby toggle' if args.action == 'toggle' else 'standby'
    elif args.command == 'wake':
        cmd = 'wake'
    elif args.command in ('send', 'tell', 'prompt', 'speak'):
        text = ' '.join(([args.action] if args.action else []) + (getattr(args, 'text_args', None) or [])).strip()
        file_path = getattr(args, 'file', None)
        if not text and not file_path:
            print(f'{args.command} requires a text message or --file to send to JARVIS', file=sys.stderr)
            return 1
        if file_path:
            import json
            resolved_file = os.path.abspath(os.path.expanduser(file_path))
            cmd = json.dumps({
                'command': 'send_input',
                'text': text,
                'file_path': resolved_file
            })
        else:
            cmd = f'{args.command} {text}'
    else:
        cmd = args.command

    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(3)
        sock.connect(str(SOCKET_PATH))
        sock.sendall((cmd + '\n').encode())
        data = sock.recv(4096)
        sock.close()
        print(data.decode().strip())
        return 0
    except Exception as e:
        print(f'IPC error: {e}', file=sys.stderr)
        return 1


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog='jarvis-voice',
        description='JARVIS Voice Core — sovereign voice foundation')
    parser.add_argument('command', nargs='?', default='run',
        choices=['run', 'status', 'listen', 'dictate', 'dictation', 'standby', 'wake', 'send', 'tell', 'prompt', 'speak', 'restart', 'disable', 'disanble', 'enable', 'start', 'stop'],
        help='Command to execute (default: run)')
    parser.add_argument('action', nargs='?', help='Action for listen/dictate or first word for send')
    parser.add_argument('text_args', nargs='*', help='Additional words for send/tell or dictation sub-action')
    parser.add_argument('--file', '-f', default=None, help='Attach an image, video, audio, or document file')
    parser.add_argument('--model', default=os.getenv('GEMINI_LIVE_MODEL'))
    parser.add_argument('--voice', default=None, help='Gemini voice name')
    parser.add_argument('--check', action='store_true',
        help='Check dependencies without opening audio or network')
    parser.add_argument('--json', action='store_true', help='Output JSON')
    parser.add_argument('--transcripts', action='store_true')
    parser.add_argument('--retries', type=int, default=5)

    args = parser.parse_args(argv)
    if args.command == 'listen' and args.action not in (None, 'toggle', 'start', 'stop', 'cancel', 'confirm', 'standby', 'dictate', 'dictation'):
        parser.error('listen action must be toggle, start, stop, cancel, confirm, standby, dictate or dictation')
    if args.command == 'listen' and args.action in ('dictate', 'dictation'):
        if len(args.text_args) > 1 or (args.text_args and args.text_args[0] not in ('start', 'stop', 'toggle', 'cancel', 'status', 'on', 'off')):
            parser.error('listen dictation action must be start, stop, toggle, cancel or status')
    if args.command in ('dictate', 'dictation') and args.action not in (None, 'start', 'stop', 'toggle', 'cancel', 'status', 'on', 'off'):
        parser.error('dictate action must be start, stop, toggle, cancel or status')
    if args.retries < 0:
        parser.error('retries must be zero or a positive integer')

    if args.check:
        missing = [n for n in ('pw-record', 'pw-play', 'pactl', 'pw-cli')
                   if shutil.which(n) is None]
        if missing:
            print(f'Missing: {", ".join(missing)}', file=sys.stderr)
            return 1
        try:
            missing_modules = [name for name in ('numpy', 'onnxruntime', 'openwakeword', 'google.genai')
                               if importlib.util.find_spec(name) is None]
            if missing_modules:
                print('Missing Python dependencies: ' + ', '.join(missing_modules), file=sys.stderr)
                return 1
            from .config import load
            config = load()
            print(f'PASS: audio commands present, config valid (model={config.model})')
            return 0
        except Exception as e:
            print(f'Config error: {e}', file=sys.stderr)
            return 1

    if args.command in ('restart', 'disable', 'disanble', 'enable', 'start', 'stop'):
        return _systemd_command(args.command)

    if args.command in ('status', 'listen', 'dictate', 'dictation', 'standby', 'wake', 'send', 'tell', 'prompt', 'speak'):
        return _ipc_command(args)

    if args.command == 'run':
        try:
            from .daemon import main as daemon_main
            return daemon_main(args)
        except ImportError as error:
            print(f'Voice dependency unavailable: {error}', file=sys.stderr)
            return 1

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
