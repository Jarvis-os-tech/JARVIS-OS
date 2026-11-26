#!/usr/bin/env bash
set -euo pipefail

launcher="$(readlink -f -- "${BASH_SOURCE[0]}")"
ui_dir="$(cd -- "$(dirname -- "$launcher")/.." && pwd)"
umask 077
session_dir="${XDG_STATE_HOME:-$HOME/.local/state}/jarvis/widget-session"
[[ ! -L "$session_dir" ]] || { echo "Widget session directory must not be a symlink" >&2; exit 1; }
mkdir -p -- "$session_dir"
chmod 700 -- "$session_dir"
exec qs --no-duplicate --path "$ui_dir/JarvisTheme.qml" "$@"
