#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/business-analysis}"
CLAUDE_INSTALL_DIR="${CLAUDE_INSTALL_DIR:-/opt/claude-code}"
MARKET_USER="${MARKET_USER:-market-ai}"
MARKET_GROUP="${MARKET_GROUP:-market-analysis}"
MARKET_DATA_DIR="${MARKET_ANALYSIS_DATA_DIR:-/var/lib/business-analysis-market}"
MARKET_LOG_DIR="${MARKET_ANALYSIS_LOG_DIR:-/var/log/business-analysis-market}"
MARKET_CONFIG_DIR="${MARKET_ANALYSIS_CONFIG_DIR:-/etc/business-analysis-market}"
MARKET_ENV_FILE="$MARKET_CONFIG_DIR/market-analysis.env"
INSTALL_CLAUDE=1
TEMP_FILES=()

cleanup_temp_files() {
  local path
  for path in "${TEMP_FILES[@]:-}"; do
    if [ -n "$path" ] && [ -f "$path" ]; then
      : > "$path" 2>/dev/null || true
      rm -f -- "$path"
    fi
  done
}
trap cleanup_temp_files EXIT HUP INT TERM

if [ "${1:-}" = "--skip-cli-install" ]; then
  INSTALL_CLAUDE=0
fi

if [ "$(id -u)" -ne 0 ]; then
  echo "请使用 sudo 运行 deploy/install-market-analysis.sh"
  exit 1
fi

if ! getent group "$MARKET_GROUP" >/dev/null; then
  groupadd --system "$MARKET_GROUP"
fi
if ! id "$MARKET_USER" >/dev/null 2>&1; then
  useradd --system --gid "$MARKET_GROUP" --home-dir /nonexistent --shell /usr/sbin/nologin "$MARKET_USER"
fi
usermod -a -G "$MARKET_GROUP" www-data

install -d -o "$MARKET_USER" -g "$MARKET_GROUP" -m 2750 "$MARKET_DATA_DIR" "$MARKET_DATA_DIR/reports" "$MARKET_DATA_DIR/home" "$MARKET_LOG_DIR"
install -d -o root -g "$MARKET_GROUP" -m 0750 "$MARKET_CONFIG_DIR"

if ! command -v claude >/dev/null 2>&1; then
  if [ "$INSTALL_CLAUDE" != "1" ]; then
    echo "ERROR: Claude Code CLI 未安装；先执行 sudo bash deploy/install-market-analysis.sh" >&2
    exit 1
  fi
  apt-get update
  apt-get install -y curl ca-certificates
  if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
    echo "ERROR: npm 安装路径需要 Node.js 18+ 和 npm；请先按 Node.js 官方方式安装。" >&2
    exit 1
  fi
  NODE_MAJOR="$(node --version | sed -E 's/^v([0-9]+).*/\1/')"
  if [ -z "$NODE_MAJOR" ] || [ "$NODE_MAJOR" -lt 18 ]; then
    echo "ERROR: Claude Code 要求 Node.js 18+，当前版本为 $(node --version)。" >&2
    exit 1
  fi
  INSTALLER="$(mktemp)"
  TEMP_FILES+=("$INSTALLER")
  if curl --proto '=https' --tlsv1.2 -fsSL https://claude.ai/install.sh -o "$INSTALLER"; then
    bash "$INSTALLER" stable
  else
    echo "Claude Code 原生安装器不可达，改用 Anthropic 官方 npm 包。"
    install -d -o root -g root -m 0755 "$CLAUDE_INSTALL_DIR"
    npm install --omit=dev --prefix "$CLAUDE_INSTALL_DIR" @anthropic-ai/claude-code@latest
  fi
  CLAUDE_SOURCE="$(command -v claude 2>/dev/null || true)"
  if [ -z "$CLAUDE_SOURCE" ] && [ -x /root/.local/bin/claude ]; then
    CLAUDE_SOURCE=/root/.local/bin/claude
  fi
  if [ -z "$CLAUDE_SOURCE" ] && [ -x "$CLAUDE_INSTALL_DIR/node_modules/.bin/claude" ]; then
    CLAUDE_SOURCE="$CLAUDE_INSTALL_DIR/node_modules/.bin/claude"
  fi
  if [ -z "$CLAUDE_SOURCE" ]; then
    echo "ERROR: Claude Code 官方安装器执行后未找到 claude" >&2
    exit 1
  fi
  CLAUDE_REAL="$(readlink -f "$CLAUDE_SOURCE")"
  install -o root -g root -m 0755 "$CLAUDE_REAL" /usr/local/bin/claude
fi

if [ ! -f "$MARKET_ENV_FILE" ]; then
  install -o root -g "$MARKET_GROUP" -m 0640 "$APP_DIR/deploy/market-analysis.env.example" "$MARKET_ENV_FILE"
  echo "已创建受保护配置模板: $MARKET_ENV_FILE"
else
  chown root:"$MARKET_GROUP" "$MARKET_ENV_FILE"
  chmod 0640 "$MARKET_ENV_FILE"
fi

ensure_env_value() {
  local key="$1"
  local value="$2"
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
  done < "$MARKET_ENV_FILE"
  if [ "$found" -eq 0 ]; then
    printf '%s=%s\n' "$key" "$value" >> "$temp"
  fi
  install -o root -g "$MARKET_GROUP" -m 0640 "$temp" "$MARKET_ENV_FILE"
  : > "$temp"
  rm -f -- "$temp"
}

ensure_env_value ANTHROPIC_MODEL 'deepseek-v4-pro[1m]'
ensure_env_value ANTHROPIC_DEFAULT_OPUS_MODEL 'deepseek-v4-pro[1m]'
ensure_env_value ANTHROPIC_DEFAULT_SONNET_MODEL 'deepseek-v4-pro[1m]'
ensure_env_value ANTHROPIC_DEFAULT_HAIKU_MODEL 'deepseek-v4-flash'
ensure_env_value CLAUDE_CODE_SUBAGENT_MODEL 'deepseek-v4-flash'
ensure_env_value MARKET_ANALYSIS_MODEL 'deepseek-v4-pro[1m]'
ensure_env_value MARKET_ANALYSIS_PRIMARY_MODEL 'deepseek-v4-pro[1m]'
ensure_env_value MARKET_ANALYSIS_REPAIR_MODEL 'deepseek-v4-flash'
ensure_env_value MARKET_ANALYSIS_ESCALATION_MODEL 'deepseek-v4-pro[1m]'
ensure_env_value MARKET_ANALYSIS_SOURCE_SCOUT_ENABLED '1'
ensure_env_value MARKET_ANALYSIS_SOURCE_SCOUT_MODEL 'deepseek-v4-flash'
ensure_env_value MARKET_ANALYSIS_SOURCE_SCOUT_MAX_TURNS '25'
ensure_env_value MARKET_ANALYSIS_SOURCE_SCOUT_MAX_BUDGET_USD '3.2'
ensure_env_value MARKET_ANALYSIS_SOURCE_SCOUT_TIMEOUT_SECONDS '900'
ensure_env_value MARKET_ANALYSIS_ZHIHU_ENABLED '1'
ensure_env_value MARKET_ANALYSIS_ZHIHU_MAX_QUERIES '4'
ensure_env_value MARKET_ANALYSIS_ZHIHU_MAX_RESULTS '12'
ensure_env_value MARKET_ANALYSIS_ZHIHU_TIMEOUT_SECONDS '20'
ensure_env_value MARKET_ANALYSIS_REPAIR_MAX_TURNS '40'
ensure_env_value MARKET_ANALYSIS_REPAIR_MAX_BUDGET_USD '3'
ensure_env_value MARKET_ANALYSIS_ESCALATION_MAX_TURNS '45'
ensure_env_value MARKET_ANALYSIS_ESCALATION_MAX_BUDGET_USD '6'
ensure_env_value MARKET_ANALYSIS_MAX_REPAIR_ATTEMPTS '2'
ensure_env_value MARKET_ANALYSIS_MIN_QUALITY_SCORE '9.0'
ensure_env_value MARKET_ANALYSIS_SOURCE_VERIFY_WORKERS '4'

install -o root -g root -m 0644 "$APP_DIR/deploy/market-analysis.service" /etc/systemd/system/market-analysis.service
install -o root -g root -m 0755 "$APP_DIR/deploy/market-analysis-schedule.sh" /usr/local/sbin/business-analysis-market-schedule
install -o root -g root -m 0644 "$APP_DIR/deploy/market-analysis-scheduled.service" /etc/systemd/system/market-analysis-scheduled.service
install -o root -g root -m 0644 "$APP_DIR/deploy/market-analysis.timer" /etc/systemd/system/market-analysis.timer
install -o root -g root -m 0755 "$APP_DIR/deploy/market-analysis-trigger.sh" /usr/local/sbin/business-analysis-market-trigger
install -o root -g root -m 0644 "$APP_DIR/deploy/market-analysis-manual.service" /etc/systemd/system/market-analysis-manual.service
install -o root -g root -m 0644 "$APP_DIR/deploy/market-analysis-manual.path" /etc/systemd/system/market-analysis-manual.path
install -o root -g root -m 0644 "$APP_DIR/deploy/market-analysis-trigger.tmpfiles" /etc/tmpfiles.d/business-analysis-market-trigger.conf
install -d -o root -g root -m 0700 /var/lib/business-analysis-market-trigger
systemd-tmpfiles --create /etc/tmpfiles.d/business-analysis-market-trigger.conf
rm -f /run/business-analysis-market-trigger/request
systemctl daemon-reload
systemctl enable --now market-analysis-manual.path

has_env_value() {
  tr -d '\r' < "$MARKET_ENV_FILE" | grep -Eq "^${1}=[^[:space:]]+$"
}

if has_env_value ANTHROPIC_AUTH_TOKEN && has_env_value AI_READONLY_TOKEN; then
  systemctl enable --now market-analysis.timer
  echo "市场研判定时器已启用：每天凌晨1点检查，到期后每3个自然日运行一次。"
else
  systemctl disable --now market-analysis.timer 2>/dev/null || true
  echo "市场研判服务已安装，但因凭据尚未安全配置，定时器未启用。"
  echo "请通过受保护方式写入 $MARKET_ENV_FILE，再执行 systemctl enable --now market-analysis.timer。"
fi

/usr/local/bin/claude --version
systemctl status market-analysis.timer --no-pager || true
