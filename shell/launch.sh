#!/usr/bin/env bash
set -euo pipefail

launcher="$(readlink -f -- "${BASH_SOURCE[0]}")"
shell_dir="$(cd -- "$(dirname -- "$launcher")" && pwd)"
umask 077
session_dir="${XDG_STATE_HOME:-$HOME/.local/state}/jarvis/widget-session"
[[ ! -L "$session_dir" ]] || { echo "Widget session directory must not be a symlink" >&2; exit 1; }
mkdir -p -- "$session_dir"
chmod 700 -- "$session_dir"
theme_path="$shell_dir/../shell.qml"
[[ -f "$theme_path" ]] || theme_path="$shell_dir/Theme.qml"
exec qs --no-duplicate --path "$theme_path" "$@"
