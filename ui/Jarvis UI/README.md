# J.A.R.V.I.S. OS — Native Desktop Orbit HUD

A native, standalone desktop overlay widget that renders a rotating cybernetic HUD orbit directly on your Wayland / Hyprland display.

> **Zero Web Dependencies**: Runs directly on Wayland via Quickshell (Qt6) hardware acceleration.  
> **Completely Draggable**: Grab the orbit with your mouse and place it anywhere across your screen.

---

## 🚀 Quick Launch

### Run Interactively:
```bash
cd "Jarvis UI"
./run.sh
```

### Run in the Background (Daemon Mode):
```bash
cd "Jarvis UI"
./run.sh --daemon
```

### Check Status:
```bash
./run.sh --status
```

### Stop the HUD:
```bash
./run.sh --stop
```

---

## 🎮 Features & Interactions

- **Rotating Cybernetic Orbit**:
  - **Outer Tactical HUD Ring**: Segments and 12-point micro-ticks rotating clockwise.
  - **Gyroscopic Ring 1**: Intermediate orbital ring with 3 glowing satellite nodes counter-rotating.
  - **Inner Gyroscopic Ring**: High-speed purple/cyan dashed orbital ring.
  - **Pulsing Arc Reactor Core**: Breathing energy core with segmented rotating vanes.
- **Full-Screen Draggability**:
  - Click and hold anywhere inside the orbit circle to drag it across your display.
  - Automatic screen edge clamping prevents the orbit from disappearing off-screen.
  - **Double-Click**: Instantly resets and docks the orbit back to bottom center.
- **HUD Telemetry Display**:
  - Displays `J.A.R.V.I.S.` tactical badge and live coordinates (`X: ... Y: ...`) while dragging.
