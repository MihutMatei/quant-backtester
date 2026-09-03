#!/usr/bin/env bash
# Install the quant bot as a systemd timer. Idempotent - safe to re-run after
# changing the units or rebuilding the image.
set -euo pipefail

UNIT_DIR=/etc/systemd/system
CONF_DIR=/etc/quant-bot
ENV_FILE="$CONF_DIR/env"
IMAGE=quant-bot:latest
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ $EUID -ne 0 ]]; then
    echo "Run as root: sudo $0" >&2
    exit 1
fi

command -v docker >/dev/null || { echo "docker is not installed" >&2; exit 1; }

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    echo "Image $IMAGE not found. Build it first:" >&2
    echo "    docker build -t $IMAGE $(dirname "$HERE")" >&2
    exit 1
fi

# Credentials: root-owned and unreadable by anyone else. Never in the repo,
# never in an image layer.
install -d -m 0750 "$CONF_DIR"
if [[ ! -f "$ENV_FILE" ]]; then
    cat > "$ENV_FILE" <<'TEMPLATE'
APCA_API_KEY_ID=
APCA_API_SECRET_KEY=
# Optional overrides - see the README for defaults.
# BOT_SYMBOL=SPY
# BOT_NOTIONAL=50000
# BOT_RSI_BUY=45
# BOT_RSI_SELL=50
TEMPLATE
    chmod 0600 "$ENV_FILE"
    echo "Created $ENV_FILE - add your Alpaca paper keys, then re-run this script."
    exit 1
fi
chmod 0600 "$ENV_FILE"

if ! grep -q '^APCA_API_KEY_ID=.\+' "$ENV_FILE"; then
    echo "$ENV_FILE has no APCA_API_KEY_ID value" >&2
    exit 1
fi

docker volume create quant-bot-state >/dev/null

install -m 0644 "$HERE/quant-bot.service" "$UNIT_DIR/"
install -m 0644 "$HERE/quant-bot.timer" "$UNIT_DIR/"
install -m 0644 "$HERE/quant-bot-failure@.service" "$UNIT_DIR/"

systemctl daemon-reload
systemctl enable --now quant-bot.timer

echo
echo "Installed. The timer fires at five past each hour."
systemctl list-timers quant-bot.timer --no-pager
echo
echo "  logs:        journalctl -u quant-bot -f"
echo "  run now:     systemctl start quant-bot.service"
echo "  failures:    systemctl list-units --failed"
echo "  stop:        systemctl disable --now quant-bot.timer"
