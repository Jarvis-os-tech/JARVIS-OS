#!/usr/bin/env bash
# ==============================================================================
# J.A.R.V.I.S. OS — Native Desktop Orbit HUD Launcher
# Runs the rotating circular HUD overlay directly on the Wayland display.
# Draggable anywhere across the screen; double-click to dock to bottom.
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
QML_FILE="${SCRIPT_DIR}/orbit.qml"
PID_FILE="${SCRIPT_DIR}/.orbit.pid"

check_running() {
    if [ -f "$PID_FILE" ]; then
        local pid
        pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        fi
    fi
    # Also check if quickshell with orbit.qml is running
    pgrep -f "quickshell.*orbit.qml" > /dev/null 2>&1
    return $?
}

stop_orbit() {
    echo "Stopping J.A.R.V.I.S. Orbit HUD..."
    if [ -f "$PID_FILE" ]; then
        local pid
        pid=$(cat "$PID_FILE")
        kill "$pid" > /dev/null 2>&1
        rm -f "$PID_FILE"
    fi
    pkill -f "quickshell.*orbit.qml" > /dev/null 2>&1 || true
    echo "Orbit HUD stopped."
}

case "$1" in
    --stop|-s)
        stop_orbit
        exit 0
        ;;
    --status)
        if check_running; then
            echo "J.A.R.V.I.S. Orbit HUD is RUNNING on Wayland display ($WAYLAND_DISPLAY)."
        else
            echo "J.A.R.V.I.S. Orbit HUD is STOPPED."
        fi
        exit 0
        ;;
    --daemon|-d)
        if check_running; then
            echo "Orbit HUD is already running. Stopping previous instance..."
            stop_orbit
            sleep 0.5
        fi
        echo "Launching J.A.R.V.I.S. Orbit HUD as a daemon..."
        nohup quickshell -p "$QML_FILE" > /dev/null 2>&1 &
        echo $! > "$PID_FILE"
        echo "Orbit HUD launched with PID $(cat "$PID_FILE")."
        echo "Drag it anywhere across your display! Double-click to dock to bottom."
        exit 0
        ;;
    *)
        if check_running; then
            echo "Orbit HUD is already running. Stopping previous instance..."
            stop_orbit
            sleep 0.5
        fi
        echo "Starting J.A.R.V.I.S. Orbit HUD (Press Ctrl+C to stop)..."
        echo "Drag it anywhere across your display! Double-click to dock to bottom."
        exec quickshell -p "$QML_FILE"
        ;;
esac
