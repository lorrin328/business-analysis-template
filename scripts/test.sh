#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v node >/dev/null 2>&1; then
  echo "Node.js 18+ is required for tax calculator tests; install it before running the test suite." >&2
  exit 1
fi
node -e "if (Number(process.versions.node.split('.')[0]) < 18) { console.error('Node.js 18+ is required for tests'); process.exit(1); }"

if [ -n "${PYTHON:-}" ]; then
  PYTHON_BIN="$PYTHON"
elif command -v python3.12 >/dev/null 2>&1; then
  PYTHON_BIN="python3.12"
elif command -v python3.11 >/dev/null 2>&1; then
  PYTHON_BIN="python3.11"
elif command -v python3.10 >/dev/null 2>&1; then
  PYTHON_BIN="python3.10"
else
  PYTHON_BIN="python3"
fi

"$PYTHON_BIN" - <<'PY'
import sys

required = (3, 10)
if sys.version_info < required:
    current = ".".join(map(str, sys.version_info[:3]))
    raise SystemExit(
        f"Python {current} is not supported. Please use Python 3.10+ for tests."
    )
PY

if [ ! -d ".venv" ]; then
  "$PYTHON_BIN" -m venv .venv
fi

. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r backend/requirements.txt
python -m pytest "$@"
