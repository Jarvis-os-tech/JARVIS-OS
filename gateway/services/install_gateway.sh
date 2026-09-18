#!/usr/bin/env bash
# Install JARVIS-OS Python Gateway as a systemd user service.
# Auto-starts on login, runs 24/7 in background.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_FILE="$SCRIPT_DIR/jarvis-gateway.service"
LEGACY_SERVICE_FILE="$SCRIPT_DIR/friday-gateway.service"
SYSTEMD_DIR="$HOME/.config/systemd/user"

echo "═══════════════════════════════════════════"
echo "  JARVIS-OS Gateway — Systemd Installer"
echo "═══════════════════════════════════════════"

PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
GATEWAY_PY="$PROJECT_DIR/brain/gateway.py"
if [ ! -f "$GATEWAY_PY" ]; then
    echo "❌ gateway.py not found at $GATEWAY_PY"
    exit 1
fi

# 2. Quick dry-run to verify imports
echo "• Verifying Python imports..."
PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
if [ ! -f "$PYTHON_BIN" ]; then
    PYTHON_BIN="python3"
fi
"$PYTHON_BIN" "$GATEWAY_PY" --dry-run || {
    echo "❌ Dry run failed. Check dependencies."
    exit 1
}

# 3. Install systemd unit & backward compatibility alias
mkdir -p "$SYSTEMD_DIR"
cp "$SERVICE_FILE" "$SYSTEMD_DIR/jarvis-gateway.service"
ln -sf "$SYSTEMD_DIR/jarvis-gateway.service" "$SYSTEMD_DIR/friday-gateway.service"
echo "• Installed service to $SYSTEMD_DIR/jarvis-gateway.service (with friday-gateway.service alias)"

# 4. Reload, enable, start
systemctl --user daemon-reload
systemctl --user enable jarvis-gateway.service
systemctl --user start jarvis-gateway.service

echo ""
echo "✅ JARVIS-OS Gateway installed and running!"
echo ""
echo "Useful commands:"
echo "  systemctl --user status jarvis-gateway"
echo "  journalctl --user -u jarvis-gateway -f"
echo "  systemctl --user restart jarvis-gateway"
echo "  systemctl --user stop jarvis-gateway"
echo "  curl http://127.0.0.1:8001/health"
echo ""
