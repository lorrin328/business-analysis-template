#!/usr/bin/env bash
set -euo pipefail
set +x

APP_DIR="${APP_DIR:-/opt/business-analysis}"
MARKET_ENV_FILE="${MARKET_ANALYSIS_ENV_FILE:-/etc/business-analysis-market/market-analysis.env}"
AI_ENV_FILE="${AI_ENV_FILE:-$APP_DIR/deploy/.ai_env}"
MARKET_GROUP="${MARKET_GROUP:-market-analysis}"

if [ "$(id -u)" -ne 0 ]; then
  echo "请使用 sudo 运行 deploy/configure-market-analysis.sh"
  exit 1
fi

if [ ! -f "$MARKET_ENV_FILE" ]; then
  echo "ERROR: 尚未安装市场研判服务：$MARKET_ENV_FILE 不存在。" >&2
  exit 1
fi

if ! command -v openssl >/dev/null 2>&1; then
  echo "ERROR: 缺少 openssl，无法在服务器本机生成只读令牌。" >&2
  exit 1
fi

echo "请输入已经轮换、未在聊天或日志中出现的新 DeepSeek API Key。"
IFS= read -r -s -p "DeepSeek API Key: " DEEPSEEK_TOKEN
echo
if [ -z "${DEEPSEEK_TOKEN//[[:space:]]/}" ]; then
  echo "ERROR: API Key 不能为空。" >&2
  exit 1
fi

AI_READONLY_TOKEN="$(openssl rand -hex 32)"
TEMP_FILES=()
cleanup() {
  local path
  for path in "${TEMP_FILES[@]:-}"; do
    [ -n "$path" ] && rm -f -- "$path"
  done
  unset DEEPSEEK_TOKEN AI_READONLY_TOKEN
}
trap cleanup EXIT

replace_env_value() {
  local target="$1"
  local key="$2"
  local value="$3"
  local owner="$4"
  local group="$5"
  local mode="$6"
  local temp line found=0

  temp="$(mktemp)"
  TEMP_FILES+=("$temp")
  if [ -f "$target" ]; then
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
  fi
  if [ "$found" -eq 0 ]; then
    printf '%s=%s\n' "$key" "$value" >> "$temp"
  fi
  install -o "$owner" -g "$group" -m "$mode" "$temp" "$target"
  : > "$temp"
}

replace_env_value "$MARKET_ENV_FILE" ANTHROPIC_AUTH_TOKEN "$DEEPSEEK_TOKEN" root "$MARKET_GROUP" 0640
replace_env_value "$MARKET_ENV_FILE" AI_READONLY_TOKEN "$AI_READONLY_TOKEN" root "$MARKET_GROUP" 0640
replace_env_value "$AI_ENV_FILE" AI_READONLY_TOKEN "$AI_READONLY_TOKEN" root root 0600

unset DEEPSEEK_TOKEN AI_READONLY_TOKEN
systemctl disable --now market-analysis.timer 2>/dev/null || true
systemctl restart business-analysis.service

APP_READY=0
for _ in $(seq 1 60); do
  if curl --fail --silent --show-error --max-time 2 \
    http://127.0.0.1:45679/api/health >/dev/null 2>&1; then
    APP_READY=1
    break
  fi
  sleep 1
done
if [ "$APP_READY" -ne 1 ]; then
  echo "ERROR: 主应用重启后 60 秒内未恢复健康，暂不启动市场研判。" >&2
  exit 1
fi

systemctl reset-failed market-analysis.service
systemctl start --no-block market-analysis.service
systemctl enable --now market-analysis.timer

echo "凭据已在服务器本机安全写入；主应用已重启，三天定时器已启用，首次研究已开始。"
