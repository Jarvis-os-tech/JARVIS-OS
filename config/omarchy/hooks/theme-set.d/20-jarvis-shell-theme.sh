#!/usr/bin/env bash
set -u

THEME_SLUG="${1:-}"

if [[ "${THEME_SLUG,,}" == "jarvis" ]]; then
  # Theme is Jarvis: Keep HUD service active and disable stock dock (CyberDock takes over)
  systemctl --user start jarvis-shell.service 2>/dev/null || true
  
  python3 -c '
import json, os
p = os.path.expanduser("~/.config/omarchy/shell.json")
try:
    with open(p) as f: cfg = json.load(f)
    dis = cfg.setdefault("disabledPlugins", [])
    if "io.github.jeocrypto.glass-dock" not in dis:
        dis.append("io.github.jeocrypto.glass-dock")
        with open(p, "w") as f: json.dump(cfg, f, indent=2)
except Exception:
    pass
'
else
  # Non-Jarvis theme: Restore stock dock for normal appearance
  python3 -c '
import json, os
p = os.path.expanduser("~/.config/omarchy/shell.json")
try:
    with open(p) as f: cfg = json.load(f)
    dis = cfg.get("disabledPlugins", [])
    if "io.github.jeocrypto.glass-dock" in dis:
        dis.remove("io.github.jeocrypto.glass-dock")
        with open(p, "w") as f: json.dump(cfg, f, indent=2)
except Exception:
    pass
'
fi
