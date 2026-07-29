#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 0 ]; then
  echo "manual market trigger does not accept arguments" >&2
  exit 64
fi

UNIT="market-analysis.service"
REQUEST_FILE="/run/business-analysis-market-trigger/request"
STATE_DIR="/var/lib/business-analysis-market-trigger"
LOCK_FILE="$STATE_DIR/trigger.lock"
STAMP_FILE="$STATE_DIR/last-trigger"
COOLDOWN_SECONDS=300

install -d -o root -g root -m 0700 "$STATE_DIR"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  exit 0
fi

rm -f -- "$REQUEST_FILE"
if systemctl is-active --quiet "$UNIT"; then
  exit 0
fi

now="$(date +%s)"
last=0
if [ -r "$STAMP_FILE" ]; then
  read -r last < "$STAMP_FILE" || last=0
fi
if [[ "$last" =~ ^[0-9]+$ ]] && [ $((now - last)) -lt "$COOLDOWN_SECONDS" ]; then
  logger -t business-analysis-market-trigger "manual trigger ignored during cooldown"
  exit 0
fi

temp_stamp="$(mktemp "$STATE_DIR/.last-trigger.XXXXXX")"
printf '%s\n' "$now" > "$temp_stamp"
chmod 0600 "$temp_stamp"
mv -f -- "$temp_stamp" "$STAMP_FILE"

systemctl reset-failed "$UNIT"
systemctl start --no-block "$UNIT"
logger -t business-analysis-market-trigger "manual market research start requested"
