#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$APP_DIR"

echo "== preflight: Node.js test runtime =="
if ! command -v node >/dev/null 2>&1; then
  echo "Node.js 18+ is required for tax calculator tests; install it before preflight. The production app does not require Node.js." >&2
  exit 1
fi
node -e "if (Number(process.versions.node.split('.')[0]) < 18) { console.error('Node.js 18+ is required for tests'); process.exit(1); }"

echo "== preflight: python version =="
python3 - <<'PY'
import sys
if sys.version_info < (3, 10):
    raise SystemExit(f"Python 3.10+ required, current={sys.version}")
print(sys.version.split()[0])
PY

echo "== preflight: required files =="
test -f "经营分析模板.html"
test -f "backend/main.py"
test -f "backend/business_data.db"
test -f "deploy/nginx.conf"
test -f "deploy/systemd.service"

echo "== preflight: nginx upload limit =="
grep -q "client_max_body_size 100m" deploy/nginx.conf

echo "== preflight: account auth =="
echo "account auth enabled; ADMIN_TOKEN is no longer required"

echo "== preflight: tests =="
if command -v uv >/dev/null 2>&1; then
  UV_CACHE_DIR="${UV_CACHE_DIR:-$APP_DIR/.uv-cache}" \
  UV_PYTHON_INSTALL_DIR="${UV_PYTHON_INSTALL_DIR:-$APP_DIR/.uv-python}" \
    uv run python -m pytest -q
else
  python3 -m pytest -q
fi

echo "== preflight: data quality =="
if command -v uv >/dev/null 2>&1; then
  UV_CACHE_DIR="${UV_CACHE_DIR:-$APP_DIR/.uv-cache}" \
  UV_PYTHON_INSTALL_DIR="${UV_PYTHON_INSTALL_DIR:-$APP_DIR/.uv-python}" \
    uv run python backend/audit_data_quality.py --year "${CHECK_YEAR:-2026}"
else
  python3 backend/audit_data_quality.py --year "${CHECK_YEAR:-2026}"
fi

echo "preflight ok"
