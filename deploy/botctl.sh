#!/usr/bin/env bash
# Operate the deployed bot. Run on the server.
#
# The timer holds the schedule; the service does one bar's work and exits.
# There is no long-running process to keep alive - "restarting the bot" means
# reloading the units and re-arming the timer.
set -euo pipefail

TIMER=quant-bot.timer
SERVICE=quant-bot.service
IMAGE=quant-bot:latest
VOLUME=quant-bot-state
ENV_FILE=/etc/quant-bot/env
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
    cat <<'USAGE'
Usage: deploy/botctl.sh <command>

  status    timer state, next fire, last run, recent decisions
  logs      follow the journal (Ctrl-C to stop)
  history   every decision so far, from the journal
  run       run one bar now (real; respects the idempotency guard)
  dry       evaluate the current bar without trading or pinging the heartbeat
  state     dump the trade log and equity points from SQLite
  pause     stop the timer - NO further trading (see the warning it prints)
  resume    start the timer again
  reload    re-read unit files after editing deploy/*.service|timer
  update    git pull, rebuild the image, re-arm the timer
USAGE
}

need_units() {
    systemctl cat "$TIMER" >/dev/null 2>&1 || {
        echo "$TIMER is not installed. Run: sudo deploy/install.sh" >&2
        exit 1
    }
}

cmd_status() {
    need_units
    echo "== timer =="
    printf '  enabled: %s\n  active:  %s\n' \
        "$(systemctl is-enabled "$TIMER" 2>&1)" "$(systemctl is-active "$TIMER" 2>&1)"
    systemctl list-timers "$TIMER" --no-pager | sed -n '2p' | sed 's/^/  /'
    echo
    echo "== last run =="
    printf '  result:   %s\n  finished: %s\n' \
        "$(systemctl show -p Result --value "$SERVICE")" \
        "$(systemctl show -p ExecMainExitTimestamp --value "$SERVICE")"
    echo
    echo "== failed units =="
    systemctl list-units --failed --no-legend | sed 's/^/  /' || true
    [[ -z "$(systemctl list-units --failed --no-legend)" ]] && echo "  none"
    echo
    echo "== recent decisions =="
    journalctl -u "$SERVICE" --no-pager -n 200 -o cat 2>/dev/null \
        | grep -E "no action|decision:|already handled|market closed|FAILED" \
        | tail -5 | sed 's/^/  /' || echo "  (none yet)"
}

cmd_logs()    { journalctl -u "$SERVICE" -f; }
cmd_history() {
    journalctl -u "$SERVICE" --no-pager -o short-iso \
        | grep -E "no action|decision:|submitted|market closed|FAILED"
}

cmd_run() { need_units; sudo systemctl start "$SERVICE"; sleep 2; \
            journalctl -u "$SERVICE" -n 8 --no-pager -o cat; }

cmd_dry() {
    # No volume, so the idempotency guard cannot suppress the decision, and
    # BOT_HEARTBEAT_URL is blanked so a diagnostic run never touches the
    # monitoring signal - a fake ping would mask a genuinely dead bot.
    docker run --rm --env-file "$ENV_FILE" \
        -e BOT_DRY_RUN=1 -e BOT_HEARTBEAT_URL= "$IMAGE"
}

cmd_state() {
    docker run --rm -v "$VOLUME":/app/data "$IMAGE" python -c "
from bot import state
conn = state.init_db('/app/data/bot.db')
trades = state.trades(conn)
print(f'{len(trades)} trade(s)')
for t in trades:
    print(f\"  {t['ts'][:19]}  {t['side']:4s} {t['qty']:.4f} {t['symbol']} \"
          f\"@ {t['price']}  {t['reason']}\")
curve = state.equity_curve(conn)
print(f'{len(curve)} equity point(s)')
for bar, eq in curve[-10:]:
    print(f'  {bar}  {eq:,.2f}')
"
}

cmd_pause() {
    need_units
    sudo systemctl stop "$TIMER"
    echo "Timer stopped. No further bars will be evaluated."
    echo
    echo "WARNING: pausing does not close anything. If the bot is holding a"
    echo "position it stays open and unmanaged - the exit signal cannot fire"
    echo "while the timer is stopped. Check before walking away:"
    echo "    deploy/botctl.sh state"
}

cmd_resume() { need_units; sudo systemctl start "$TIMER"; \
               systemctl list-timers "$TIMER" --no-pager | sed -n '1,2p'; }

cmd_reload() {
    sudo install -m 0644 "$REPO"/deploy/quant-bot.service \
        "$REPO"/deploy/quant-bot.timer \
        "$REPO"/deploy/quant-bot-failure@.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl restart "$TIMER"
    echo "Units reinstalled and timer re-armed."
    systemctl list-timers "$TIMER" --no-pager | sed -n '2p'
}

cmd_update() {
    cd "$REPO"
    git pull
    docker build -t "$IMAGE" .
    cmd_reload
    echo
    echo "The next fire uses the new image. Verify with: deploy/botctl.sh dry"
}

case "${1:-}" in
    status)  cmd_status ;;
    logs)    cmd_logs ;;
    history) cmd_history ;;
    run)     cmd_run ;;
    dry)     cmd_dry ;;
    state)   cmd_state ;;
    pause)   cmd_pause ;;
    resume)  cmd_resume ;;
    reload)  cmd_reload ;;
    update)  cmd_update ;;
    *)       usage; exit 1 ;;
esac
