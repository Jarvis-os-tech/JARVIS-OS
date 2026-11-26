"""User-local NVIDIA NIM planning service for CLI Agent development jobs."""

import asyncio
import json
import os
from pathlib import Path

from .planning import plan_connection

LIMIT = 65536


def socket_path():
    return Path(os.getenv('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}')) / 'jarvis-cli-agent/control.sock'


async def request(operation, arguments):
    packet = (json.dumps({'operation': operation, 'arguments': arguments}, ensure_ascii=False) + '\n').encode()
    if len(packet) > LIMIT:
        raise ValueError('CLI Agent request exceeds the size limit')
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_unix_connection(str(socket_path()), limit=LIMIT), 2)
    except (OSError, TimeoutError) as error:
        raise ValueError('CLI Agent service is unavailable') from error
    try:
        writer.write(packet)
        await asyncio.wait_for(writer.drain(), 2)
        result = json.loads(await asyncio.wait_for(reader.readline(), 40))
        if not isinstance(result, dict):
            raise ValueError('Invalid CLI Agent response')
    except (OSError, ValueError, TimeoutError) as error:
        raise ValueError('CLI Agent service did not return a complete response') from error
    finally:
        writer.close()
    if not result.get('ok'):
        raise ValueError(result.get('error', 'CLI Agent request failed'))
    return result


class CLIAgentService:
    def __init__(self):
        self.planning = False

    async def handle(self, reader, writer):
        try:
            packet = json.loads(await asyncio.wait_for(reader.readline(), 3))
            if not isinstance(packet, dict):
                raise ValueError('Expected a CLI Agent request object')
            operation, arguments = packet.get('operation'), packet.get('arguments')
            if operation == 'health' and arguments == {}:
                result = {'ok': True, 'service': 'jarvis-cli-agent', 'scope': 'transport_only'}
            elif operation == 'plan' and isinstance(arguments, dict) and set(arguments) == {'request'}:
                task = arguments['request']
                if not isinstance(task, str) or not 1 <= len(task.strip()) <= 12000:
                    raise ValueError('Connection request must be 1 to 12000 characters')
                if self.planning:
                    raise ValueError('CLI Agent is already planning a connection')
                self.planning = True
                try:
                    result = {'ok': True, 'plan': await asyncio.to_thread(plan_connection, task)}
                finally:
                    self.planning = False
            else:
                raise ValueError('Unknown CLI Agent operation or invalid arguments')
        except (ValueError, TimeoutError) as error:
            result = {'ok': False, 'error': str(error) or 'CLI Agent request timed out'}
        except Exception:
            result = {'ok': False, 'error': 'CLI Agent planning failed'}
        try:
            writer.write((json.dumps(result) + '\n').encode())
            await asyncio.wait_for(writer.drain(), 2)
        except (OSError, TimeoutError):
            pass
        finally:
            writer.close()


async def serve():
    path = socket_path()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.parent.is_symlink() or path.parent.stat().st_uid != os.getuid():
        raise RuntimeError('Unsafe CLI Agent socket directory')
    path.parent.chmod(0o700)
    if os.path.lexists(path):
        if path.is_symlink() or not path.is_socket():
            raise RuntimeError('CLI Agent socket path is occupied')
        try:
            _, writer = await asyncio.open_unix_connection(str(path))
        except ConnectionRefusedError:
            path.unlink()
        else:
            writer.close()
            raise RuntimeError('CLI Agent service already has a listener')
    server = await asyncio.start_unix_server(CLIAgentService().handle, str(path), limit=LIMIT)
    path.chmod(0o600)
    async with server:
        await server.serve_forever()


if __name__ == '__main__':
    asyncio.run(serve())
