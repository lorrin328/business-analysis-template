#!/usr/bin/env bash
set -euo pipefail

DATA_DIR="${MARKET_ANALYSIS_DATA_DIR:-/var/lib/business-analysis-market}"
LATEST_FILE="$DATA_DIR/latest.json"
SERVICE_NAME="${MARKET_ANALYSIS_SERVICE_NAME:-market-analysis.service}"
LOCK_FILE="${MARKET_ANALYSIS_SCHEDULE_LOCK:-/run/business-analysis-market-schedule/schedule.lock}"
SYSTEMCTL_BIN="${MARKET_ANALYSIS_SYSTEMCTL:-/usr/bin/systemctl}"
PYTHON_BIN="${MARKET_ANALYSIS_PYTHON:-/usr/bin/python3}"

mkdir -p "$(dirname "$LOCK_FILE")"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "市场研判定时检查已有实例运行，本次跳过。"
  exit 0
fi

if "$SYSTEMCTL_BIN" is-active --quiet "$SERVICE_NAME"; then
  echo "市场研判服务正在运行，本次定时检查跳过。"
  exit 0
fi

SHOULD_RUN=$("$PYTHON_BIN" - "$LATEST_FILE" <<'PY'
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

latest_file = Path(sys.argv[1])
today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
if not latest_file.exists():
    print("1")
    raise SystemExit(0)

report = json.loads(latest_file.read_text(encoding="utf-8"))
generated_at = datetime.fromisoformat(str(report["generatedAt"]).replace("Z", "+00:00"))
if generated_at.tzinfo is None:
    raise ValueError("latest report generatedAt must include a timezone")
report_date = generated_at.astimezone(ZoneInfo("Asia/Shanghai")).date()
print("1" if today >= report_date + timedelta(days=3) else "0")
PY
)

if [ "$SHOULD_RUN" != "1" ]; then
  echo "距上次成功报告尚未满3个自然日，本次凌晨1点检查不启动研究。"
  exit 0
fi

"$SYSTEMCTL_BIN" start --no-block "$SERVICE_NAME"
echo "已到3个自然日周期，市场研判研究已于凌晨1点启动。"
