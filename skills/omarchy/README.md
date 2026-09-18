# ⚡ Omarchy Skills — High-Performance OS Actuators for JARVIS-OS

A native, hybrid C++17 and Python desktop automation engine for Omarchy Linux and Hyprland.
Executes desktop actions in fractions of a second (sub-1ms to 20ms) via direct Unix domain socket IPC and optimized process execution.

---

## Architecture

```
omarchy_skills/
├── bin/
│   └── omarchy_ctrl       # Compiled C++17 binary (sub-millisecond socket actuator)
├── cpp/
│   ├── Makefile           # Compiler flags: -O3 -Wall -Wextra -std=c++17
│   └── omarchy_ctrl.cpp   # Direct Hyprland Lua socket IPC + Omarchy actuator
├── python/                # Modular Python domain libraries
│   ├── __init__.py
│   ├── hyprland.py        # Window close, fullscreen, float, workspace jumping
│   ├── theme.py           # Theme switching, wallpaper cycling, switcher UI
│   ├── toggles.py         # Nightlight, bar, touchpad, screensaver, stay-awake
│   ├── system.py          # Lock screen, sleep, audio/wifi restart, OSD banners
│   ├── capture.py         # Screenshots (smart/fullscreen), OCR text, QR decode
│   └── launcher.py        # Terminal, browser, editor, Spotify launchers
├── __init__.py            # Root Python package entrypoint
└── README.md              # Documentation
```

---

## Benchmarked Latency

| Action | Transport | Latency |
|---|---|---|
| **Hyprland Window Close / Float / Fullscreen** | Unix Domain Socket (`.socket.sock`) | **< 0.5 ms** |
| **Workspace Jump (`workspace 1..10`)** | Unix Domain Socket (`.socket.sock`) | **< 1.0 ms** |
| **Active Window Inspection** | Hyprland JSON IPC | **~ 5.0 ms** |
| **Cycle Theme / Wallpaper (`theme bg next`)** | Native C++ process runner | **~ 10.0 ms** |
| **Nightlight Toggle (`toggle nightlight`)** | Native C++ process runner | **~ 12.0 ms** |
| **Service Restart (Audio / Wi-Fi / Shell)** | Native C++ systemd runner | **~ 25.0 ms** |

---

## Python Usage

```python
import asyncio
from omarchy_skills import OmarchySkills, execute_omarchy_action

# Direct domain call
async def main():
    # 1. Switch wallpaper / background
    await OmarchySkills.theme.next_background()

    # 2. Toggle nightlight
    await OmarchySkills.toggles.toggle_nightlight()

    # 3. Jump workspace
    await OmarchySkills.hyprland.switch_workspace(2)

    # 4. Universal functional action
    res = await execute_omarchy_action("hypr", "fullscreen")
    print(res)

asyncio.run(main())
```

---

## C++ CLI Usage

```bash
# Direct binary execution
./omarchy_skills/bin/omarchy_ctrl hypr close_window
./omarchy_skills/bin/omarchy_ctrl hypr workspace 3
./omarchy_skills/bin/omarchy_ctrl theme next_bg
./omarchy_skills/bin/omarchy_ctrl toggle nightlight
./omarchy_skills/bin/omarchy_ctrl restart audio
./omarchy_skills/bin/omarchy_ctrl osd "JARVIS Online"
```
