#!/usr/bin/env bash
set -euo pipefail
set +x

APP_DIR="${APP_DIR:-/opt/business-analysis}"
MARKET_ENV_FILE="${MARKET_ANALYSIS_ENV_FILE:-/etc/business-analysis-market/market-analysis.env}"
MARKET_USER="${MARKET_USER:-market-ai}"
MARKET_GROUP="${MARKET_GROUP:-market-analysis}"
TEMP_FILES=()

cleanup() {
  local path
  for path in "${TEMP_FILES[@]:-}"; do
    if [ -n "$path" ] && [ -f "$path" ]; then
      : > "$path" 2>/dev/null || true
      rm -f -- "$path"
    fi
  done
  unset ZHIHU_SECRET
}
trap cleanup EXIT HUP INT TERM

if [ "$(id -u)" -ne 0 ]; then
  echo "请使用 sudo 运行 deploy/configure-zhihu-api.sh"
  exit 1
fi
if [ ! -f "$MARKET_ENV_FILE" ]; then
  echo "ERROR: 市场研判配置不存在：$MARKET_ENV_FILE" >&2
  exit 1
fi
if [ ! -x "$APP_DIR/backend/venv/bin/python" ]; then
  echo "ERROR: 市场研判Python环境不存在。" >&2
  exit 1
fi

IFS= read -r -s -p "知乎 Access Secret: " ZHIHU_SECRET </dev/tty
echo
if [ -z "${ZHIHU_SECRET//[[:space:]]/}" ] || [[ "$ZHIHU_SECRET" =~ [[:space:]] ]] || [ "${#ZHIHU_SECRET}" -lt 20 ]; then
  echo "ERROR: Access Secret 格式无效。" >&2
  exit 1
fi

replace_env_value() {
  local target="$1"
  local key="$2"
  local value="$3"
  local temp line found=0
  temp="$(mktemp)"
  TEMP_FILES+=("$temp")
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line%$'\r'}"
    case "$line" in
      "$key="*)
        printf '%s=%s\n' "$key" "$value" >> "$temp"
        found=1
        ;;
      *) printf '%s\n' "$line" >> "$temp" ;;
    esac
  done < "$target"
  if [ "$found" -eq 0 ]; then
    printf '%s=%s\n' "$key" "$value" >> "$temp"
  fi
  install -o root -g "$MARKET_GROUP" -m 0640 "$temp" "$target"
  : > "$temp"
}

backup="$(mktemp)"
TEMP_FILES+=("$backup")
cp --preserve=mode,ownership "$MARKET_ENV_FILE" "$backup"
replace_env_value "$MARKET_ENV_FILE" ZHIHU_ACCESS_SECRET "$ZHIHU_SECRET"
replace_env_value "$MARKET_ENV_FILE" MARKET_ANALYSIS_ZHIHU_ENABLED 1
unset ZHIHU_SECRET

if ! runuser -u "$MARKET_USER" -- bash -lc "
  set -a
  source '$MARKET_ENV_FILE'
  set +a
  cd '$APP_DIR/backend'
  ./venv/bin/python - <<'PY'
from market_analysis.zhihu_api import search_zhihu

payload = search_zhihu('寿险 市场')
if not isinstance(payload, (dict, list)):
    raise RuntimeError('Zhihu API returned an unexpected payload type')
print('知乎官方API鉴权成功。')
PY
"; then
  install -o root -g "$MARKET_GROUP" -m 0640 "$backup" "$MARKET_ENV_FILE"
  echo "ERROR: 知乎API验证失败，已恢复原配置。" >&2
  exit 1
fi

runuser -u "$MARKET_USER" -- bash -lc "
  set -a
  source '$MARKET_ENV_FILE'
  set +a
  cd '$APP_DIR/backend'
  ./venv/bin/python run_market_research.py --zhihu-scout-only
"

echo "知乎API已写入受保护配置；下一次来源侦察将自动启用，不会立即发布报告。"
