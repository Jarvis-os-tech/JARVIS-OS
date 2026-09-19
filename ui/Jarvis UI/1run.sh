#!/usr/bin/env bash
# ==============================================================================
# J.A.R.V.I.S. OS — Sovereign AI Operating System Unified Launcher
# Launches both the Core Backend (PipeWire audio + Gemini Live + IPC)
# and the Native Wayland Orbit HUD UI (Quickshell Qt6).
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JARVIS_DIR="${SCRIPT_DIR}/jarvis"
UI_DIR="${SCRIPT_DIR}/Jarvis UI"
QML_FILE="${UI_DIR}/orbit.qml"

CORE_PID_FILE="${SCRIPT_DIR}/.jarvis_core.pid"
UI_PID_FILE="${SCRIPT_DIR}/.jarvis_ui.pid"

is_core_running() {
    if curl -s --max-time 1 http://127.0.0.1:3000/api/health > /dev/null 2>&1; then
        return 0
    fi
    if [ -f "$CORE_PID_FILE" ]; then
        local pid
        pid=$(cat "$CORE_PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        fi
    fi
    pgrep -f "tsx.*server.ts" > /dev/null 2>&1 || pgrep -f "node.*server.cjs" > /dev/null 2>&1
    return $?
}

is_ui_running() {
    if pgrep -f "quickshell.*orbit.qml" > /dev/null 2>&1; then
        return 0
    fi
    if [ -f "$UI_PID_FILE" ]; then
        local pid
        pid=$(cat "$UI_PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

stop_all() {
    echo "Stopping J.A.R.V.I.S. OS..."
    
    # 1. Stop Orbit HUD UI
    if [ -f "$UI_PID_FILE" ]; then
        local ui_pid
        ui_pid=$(cat "$UI_PID_FILE")
        kill "$ui_pid" > /dev/null 2>&1 || true
        rm -f "$UI_PID_FILE"
    fi
    pkill -f "quickshell.*orbit.qml" > /dev/null 2>&1 || true
    echo "  ✔ Orbit HUD UI stopped."

    # 2. Stop Core Backend
    if [ -f "$CORE_PID_FILE" ]; then
        local core_pid
        core_pid=$(cat "$CORE_PID_FILE")
        kill "$core_pid" > /dev/null 2>&1 || true
        rm -f "$CORE_PID_FILE"
    fi
    pkill -f "tsx.*server.ts" > /dev/null 2>&1 || true
    pkill -f "node.*server.cjs" > /dev/null 2>&1 || true
    pkill -f "pw-record.*16000" > /dev/null 2>&1 || true
    pkill -f "pw-play.*24000" > /dev/null 2>&1 || true
    rm -f /tmp/jarvis_ipc.sock /tmp/jarvis_state.json
    echo "  ✔ Core Backend stopped."

    echo "J.A.R.V.I.S. OS is completely stopped."
}

show_status() {
    echo "=================================================================="
    echo "            J.A.R.V.I.S. OS — SYSTEM STATUS                       "
    echo "=================================================================="
    
    if is_core_running; then
        echo "  Core Backend : [RUNNING] (Port 3000, PipeWire Audio active)"
    else
        echo "  Core Backend : [STOPPED]"
    fi

    if is_ui_running; then
        echo "  Orbit HUD UI : [RUNNING] (Quickshell Wayland Overlay)"
    else
        echo "  Orbit HUD UI : [STOPPED]"
    fi

    if [ -S "/tmp/jarvis_ipc.sock" ]; then
        echo "  IPC Socket   : [ACTIVE]  (/tmp/jarvis_ipc.sock)"
    else
        echo "  IPC Socket   : [INACTIVE]"
    fi

    if [ -f "/tmp/jarvis_state.json" ]; then
        echo "  State JSON   : $(cat /tmp/jarvis_state.json)"
    fi
    echo "=================================================================="
}

start_core_daemon() {
    if is_core_running; then
        echo "Core Backend is already running."
        return 0
    fi
    echo "Starting J.A.R.V.I.S. Core Backend..."
    setsid "$JARVIS_DIR/node_modules/.bin/tsx" "$JARVIS_DIR/server.ts" > "${SCRIPT_DIR}/.jarvis_core.log" 2>&1 &
    echo $! > "$CORE_PID_FILE"
    
    # Wait for IPC socket or HTTP port
    for i in {1..50}; do
        if curl -s http://127.0.0.1:3000/api/health > /dev/null 2>&1; then
            break
        fi
        sleep 0.1
    done
    echo "  ✔ Core Backend launched (PID: $(cat "$CORE_PID_FILE" 2>/dev/null || echo '?'))."
}

start_ui_daemon() {
    if is_ui_running; then
        echo "Orbit HUD UI is already running."
        return 0
    fi
    echo "Starting J.A.R.V.I.S. Orbit HUD UI..."
    setsid quickshell -p "$QML_FILE" > "${SCRIPT_DIR}/.jarvis_ui.log" 2>&1 &
    echo $! > "$UI_PID_FILE"
    sleep 0.5
    echo "  ✔ Orbit HUD UI launched (PID: $(cat "$UI_PID_FILE" 2>/dev/null || echo '?'))."
}

case "$1" in
    --stop|-s)
        stop_all
        exit 0
        ;;
    --status)
        show_status
        exit 0
        ;;
    --daemon|-d)
        start_core_daemon
        start_ui_daemon
        echo ""
        echo "J.A.R.V.I.S. OS is now running in the background."
        echo "Directives:"
        echo "  • Voice: Speak naturally to Jarvis through your microphone."
        echo "  • Standby: Click the Orbit HUD once to toggle Standby/Active."
        echo "  • Docking: Double-click the Orbit HUD to re-dock to bottom."
        echo "  • Drag: Grab and move the Orbit HUD anywhere on your display."
        echo "  • Stop: Run ./run.sh --stop"
        exit 0
        ;;
    speak)
        shift
        MESSAGE="$*"
        if [ -z "$MESSAGE" ]; then
            MESSAGE="Good evening Sir, J.A.R.V.I.S. OS systems are fully online and operational."
        fi
        curl -s -X POST http://127.0.0.1:3000/api/speak \
            -H "Content-Type: application/json" \
            -d "{\"text\": \"$MESSAGE\"}"
        echo ""
        exit 0
        ;;
    toggle)
        curl -s -X POST http://127.0.0.1:3000/api/standby/toggle
        echo ""
        exit 0
        ;;
    screen)
        curl -s -X POST http://127.0.0.1:3000/api/vision/screen
        echo ""
        exit 0
        ;;
    camera)
        curl -s -X POST http://127.0.0.1:3000/api/vision/camera
        echo ""
        exit 0
        ;;
    search)
        shift
        curl -s -X POST http://127.0.0.1:3000/api/grounding/search \
            -H "Content-Type: application/json" \
            -d "{\"query\": \"$*\"}"
        echo ""
        exit 0
        ;;
    --ui-only)
        echo "Launching Orbit HUD UI only..."
        exec quickshell -p "$QML_FILE"
        ;;
    --core-only)
        echo "Launching Core Backend only..."
        exec setsid "$JARVIS_DIR/node_modules/.bin/tsx" "$JARVIS_DIR/server.ts"
        ;;
    *)
        # Interactive Run: boots both, traps Ctrl+C, shows combined execution
        echo "=================================================================="
        echo "       J.A.R.V.I.S. OS — SOVEREIGN VOICE & HUD LAUNCHER           "
        echo "=================================================================="
        
        # Stop any existing stale daemons
        if is_core_running || is_ui_running; then
            echo "Stopping previous running instances..."
            stop_all
            sleep 0.5
        fi

        # Trap Ctrl+C and exit cleanly
        trap 'echo ""; stop_all; exit 0' INT TERM

        # 1. Start Core Backend in background of this process group
        echo "Starting Core Backend (PipeWire Audio + Gemini Live)..."
        npx --prefix "$JARVIS_DIR" tsx "$JARVIS_DIR/server.ts" &
        CORE_PROC_PID=$!
        echo "$CORE_PROC_PID" > "$CORE_PID_FILE"

        # Wait for IPC socket or HTTP port
        for i in {1..40}; do
            if curl -s http://127.0.0.1:3000/api/health > /dev/null 2>&1; then
                break
            fi
            sleep 0.1
        done

        # 2. Launch Orbit HUD UI
        echo "Launching Native Wayland Orbit HUD UI (Press Ctrl+C to terminate)..."
        quickshell -p "$QML_FILE" &
        UI_PROC_PID=$!
        echo "$UI_PROC_PID" > "$UI_PID_FILE"

        # Wait on either process
        wait $UI_PROC_PID || true
        stop_all
        ;;
esac
