#!/usr/bin/env python3
"""Send a fixture event to the local JARVIS HUD preview."""

from __future__ import annotations

import argparse
from pathlib import Path
import socket
import sys
import uuid

if __package__:
    from . import protocol
else:
    import protocol


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog='Example: spawn_widget demo --payload \'{"kind":"text","title":"Preview","data":{"text":"Hello"}}\'',
    )
    parser.add_argument("action_or_event", help="action name, a complete JSON event, or demo")
    parser.add_argument("id", nargs="?", help="widget id for action form")
    parser.add_argument("--payload", help="JSON object for action form")
    parser.add_argument("--socket", type=Path, default=protocol.socket_path(), help="override the preview socket")
    parser.add_argument("--dry-run", action="store_true", help="print the validated message")
    args = parser.parse_args(argv)

    try:
        if args.action_or_event.lstrip().startswith("{"):
            if args.id is not None or args.payload is not None:
                raise protocol.ProtocolError("raw JSON event already contains its id and payload")
            event = protocol.decode_frame((args.action_or_event + "\n").encode("utf-8"))
        else:
            event = {"action": args.action_or_event}
            if args.id is not None:
                event["id"] = args.id
            if args.payload is not None:
                event["payload"] = protocol.decode_frame((args.payload + "\n").encode("utf-8"))
        events = [event]
        if args.action_or_event == "demo":
            if args.id is not None or args.payload is not None:
                raise protocol.ProtocolError("demo does not accept a widget ID or payload")
            prefix = "hud-demo-" + uuid.uuid4().hex[:8]
            events = [
                {"action": "spawn_widget", "id": f"{prefix}-{index}",
                 "payload": {"kind": "text", "title": f"Demo card {index + 1}",
                             "side": "left" if index < 4 else "right",
                             "expires_seconds": 60, "data": {"text": "HUD layout check"}}}
                for index in range(6)
            ]
        for item in events:
            line = protocol.encode_event(item)
            if args.dry_run:
                sys.stdout.buffer.write(line)
                continue
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
                connection.settimeout(2)
                connection.connect(str(args.socket))
                connection.sendall(line)
                with connection.makefile("rb") as stream:
                    reply_line = stream.readline(protocol.MAX_EVENT_BYTES + 1)
            reply = protocol.decode_frame(reply_line)
            if not isinstance(reply, dict) or not isinstance(reply.get("ok"), bool):
                raise protocol.ProtocolError("preview did not return a valid acknowledgment")
            if not reply["ok"]:
                raise protocol.ProtocolError(str(reply.get("error") or "preview rejected the event"))
    except (OSError, ValueError, RecursionError) as exc:
        print(f"Widget preview: {exc}", file=sys.stderr)
        return 1
    if not args.dry_run:
        print(f"Widget preview accepted {len(events)} event(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
