#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/business-analysis}"
SERVICE_NAME="${SERVICE_NAME:-business-analysis}"
RUN_USER="${RUN_USER:-www-data}"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-/opt/business-analysis-backups}"
DATA_DIR="${DATA_DIR:-/var/lib/business-analysis}"
LOG_DIR="${BUSINESS_ANALYSIS_LOG_DIR:-/var/log/business-analysis}"
DB_PATH="${BUSINESS_ANALYSIS_DB:-$DATA_DIR/business_data.db}"
LEGACY_DB_PATH="$APP_DIR/backend/business_data.db"
export BUSINESS_ANALYSIS_DB="$DB_PATH"
export BUSINESS_ANALYSIS_LOG_DIR="$LOG_DIR"
# auto: 首次部署且存在足够 Excel 时才全量重建；已有生产库默认保护页面上传数据。
REBUILD_DATABASE="${REBUILD_DATABASE:-auto}"

if [ "$(id -u)" -ne 0 ]; then
  echo "请使用 sudo 运行 deploy/deploy.sh"
  exit 1
fi

apt-get update
apt-get install -y python3 python3-venv python3-pip nginx rsync

PYTHON_VERSION_OK=$(python3 - <<'PY'
import sys
print("1" if sys.version_info >= (3, 10) else "0")
PY
)
if [ "$PYTHON_VERSION_OK" != "1" ]; then
  echo "ERROR: Python 3.10+ is required. Current version: $(python3 --version 2>&1)"
  echo "Please install Python 3.10 or newer before running this deploy script."
  exit 1
fi

mkdir -p "$APP_DIR" "$BACKUP_DIR" "$DATA_DIR" "$LOG_DIR"

# 自动部署链路曾允许 www-data 执行项目树内可写脚本。正式安全方案落地前关闭该链路，
# 仅保留由管理员通过可信发布包手工执行本脚本的方式。
systemctl disable --now webhook-deploy 2>/dev/null || true
rm -f /etc/sudoers.d/webhook-deploy

SERVICE_WAS_ACTIVE=0
if systemctl is-active --quiet "$SERVICE_NAME"; then
  SERVICE_WAS_ACTIVE=1
  systemctl stop "$SERVICE_NAME"
fi

restore_service_on_error() {
  local exit_code=$?
  echo "ERROR: 部署中止，尝试恢复原服务" >&2
  if [ "$SERVICE_WAS_ACTIVE" = "1" ]; then
    systemctl start "$SERVICE_NAME" 2>/dev/null || true
  fi
  exit "$exit_code"
}
trap restore_service_on_error ERR

# 首次切换到专用运行数据目录时，使用 SQLite Online Backup API 迁移旧运行库。
if [ ! -f "$DB_PATH" ] && [ -f "$LEGACY_DB_PATH" ]; then
  echo "正在将生产数据库迁移到独立数据目录: $DB_PATH"
  python3 "$SRC_DIR/backend/backup_database.py" \
    --source "$LEGACY_DB_PATH" \
    --destination "$DB_PATH"
fi

DB_EXISTED_BEFORE=0
if [ -f "$DB_PATH" ]; then
  DB_EXISTED_BEFORE=1
fi
# 只要生产数据库存在就备份，避免有经营数据/权限数据但目标配置为空时漏备份。
if [ -f "$DB_PATH" ]; then
  BACKUP_TS="$(date +%Y%m%d_%H%M%S)"
  BACKUP_FILE="$BACKUP_DIR/business_data.db.$BACKUP_TS"
  python3 "$SRC_DIR/backend/backup_database.py" \
    --source "$DB_PATH" \
    --destination "$BACKUP_FILE" \
    --meta "$BACKUP_FILE.meta"
  echo "已备份数据库: $BACKUP_FILE"
fi

rsync -a --delete \
  --exclude='.git' \
  --exclude='node_modules' \
  --exclude='backend/__pycache__' \
  --exclude='backend/venv' \
  --exclude='backend/logs/*.log' \
  --exclude='deploy/.admin_env' \
  --exclude='deploy/.ai_env' \
  --exclude='deploy/.webhook_env' \
  --exclude='*.xlsx' \
  --exclude='*.db' \
  "$SRC_DIR/" "$APP_DIR/"

rm -rf "$APP_DIR/backend/venv"
python3 -m venv "$APP_DIR/backend/venv"
"$APP_DIR/backend/venv/bin/pip" install --upgrade pip
"$APP_DIR/backend/venv/bin/pip" install -r "$APP_DIR/backend/requirements.txt"

cd "$APP_DIR/backend"
"$APP_DIR/backend/venv/bin/python" -c "from db import init_db; init_db()"

# 从所有备份中自动找出目标数据最多的那个恢复
bash "$APP_DIR/deploy/recover_targets.sh" || echo '⚠ 目标数据恢复失败，请检查备份目录'

# 如果备份恢复后仍无目标数据，从 targets_import.json 导入（Excel 解析的预设目标）
if [ -f "$APP_DIR/targets_import.json" ]; then
  HAS_TARGETS=$("$APP_DIR/backend/venv/bin/python" -c "
import sqlite3, json, os
db='$DB_PATH'
if os.path.exists(db):
    c=sqlite3.connect(db)
    n=c.execute('SELECT COUNT(*) FROM target_config').fetchone()[0]
    c.close()
    print(n)
else:
    print(0)
" 2>/dev/null || echo "0")
  if [ "$HAS_TARGETS" = "0" ]; then
    echo "从 targets_import.json 导入预设目标..."
    "$APP_DIR/backend/venv/bin/python" -c "
import json, sys
sys.path.insert(0, '$APP_DIR/backend')
from db import save_target_config
with open('$APP_DIR/targets_import.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
result = save_target_config(data['year'], data, updated_by='deploy')
print(f'已导入 {data[\"year\"]} 年目标配置')
" && echo '✓ 预设目标导入成功' || echo '⚠ 预设目标导入失败'
  fi
fi

# 数据重建策略：
# - 默认 auto：已有生产库时不再使用服务器目录里的 Excel 全量重建，避免旧 Excel 覆盖 Web 上传数据；
# - 首次部署无数据库且存在足够 Excel 时自动重建；
# - 如确需从 Excel 强制重建，执行：REBUILD_DATABASE=1 sudo bash deploy/deploy.sh。
EXCEL_COUNT=$(find "$APP_DIR" -maxdepth 1 -name "*.xlsx" 2>/dev/null | wc -l)
REBUILD_MODE="$(printf '%s' "$REBUILD_DATABASE" | tr '[:upper:]' '[:lower:]')"
SHOULD_REBUILD_FROM_EXCEL=0
case "$REBUILD_MODE" in
  1|true|yes|excel|force)
    SHOULD_REBUILD_FROM_EXCEL=1
    ;;
  0|false|no|skip|raw|none)
    SHOULD_REBUILD_FROM_EXCEL=0
    ;;
  auto|"")
    if [ "$DB_EXISTED_BEFORE" = "0" ] && [ "$EXCEL_COUNT" -ge 3 ]; then
      SHOULD_REBUILD_FROM_EXCEL=1
    fi
    ;;
  *)
    echo "ERROR: REBUILD_DATABASE must be auto, 1, or 0. Current: $REBUILD_DATABASE" >&2
    exit 1
    ;;
esac

if [ "$SHOULD_REBUILD_FROM_EXCEL" = "1" ]; then
  if [ "$EXCEL_COUNT" -lt 3 ]; then
    echo "ERROR: REBUILD_DATABASE=$REBUILD_DATABASE 但 Excel 文件不足（需 ≥3），无法全量重建数据库。"
    exit 1
  fi
  echo "检测到 $EXCEL_COUNT 个 Excel 文件，正在重建数据库..."
  "$APP_DIR/backend/venv/bin/python" "$APP_DIR/backend/rebuild_from_excels.py" || {
    echo "ERROR: 数据库重建失败，部署已中止。请检查 Excel 文件名、字段和重建日志。"
    exit 1
  }
else
  if [ "$DB_EXISTED_BEFORE" = "1" ]; then
    echo "检测到已有生产数据库，默认不从 Excel 全量重建；如需强制重建请设置 REBUILD_DATABASE=1"
  else
    echo "⚠ 未检测到已有生产数据库，且 Excel 文件不足（需 ≥3），跳过 Excel 全量重建"
  fi
  echo "  尝试从 SQLite 原始明细表重建聚合..."
  "$APP_DIR/backend/venv/bin/python" "$APP_DIR/backend/rebuild_aggregates_from_raw_tables.py" || {
    echo "ERROR: SQLite 原始表重建失败，部署已中止，避免以空聚合或旧聚合继续上线。" >&2
    exit 1
  }
fi

echo "Account auth enabled; ADMIN_TOKEN is no longer required."

cp "$APP_DIR/deploy/systemd.service" "/etc/systemd/system/${SERVICE_NAME}.service"
cp "$APP_DIR/deploy/nginx.conf" /etc/nginx/sites-available/business-analysis
ln -sf /etc/nginx/sites-available/business-analysis /etc/nginx/sites-enabled/business-analysis
rm -f /etc/nginx/sites-enabled/default

# 验证 nginx 配置（client_max_body_size 必须包含）
if ! grep -q "client_max_body_size" /etc/nginx/sites-available/business-analysis; then
  echo "⚠ 警告：nginx 配置缺少 client_max_body_size，大文件上传将被拒绝（413 错误）"
fi

# 应用代码只读；仅独立的数据目录和日志目录允许应用账号写入。
chown -R root:root "$APP_DIR"
chown -R "$RUN_USER:$RUN_USER" "$DATA_DIR" "$LOG_DIR"
chmod 750 "$DATA_DIR" "$LOG_DIR"
if [ -f "$DB_PATH" ]; then
  chmod 640 "$DB_PATH"
fi
for runtime_env in "$APP_DIR/deploy/.admin_env" "$APP_DIR/deploy/.ai_env" "$APP_DIR/deploy/.webhook_env"; do
  if [ -f "$runtime_env" ]; then
    chown root:"$RUN_USER" "$runtime_env"
    chmod 640 "$runtime_env"
  fi
done

# Claude Code 已安装时同步市场研判的隔离账号、目录、服务和三天定时器；
# 未安装时不影响经营看板主服务，首次安装使用 deploy/install-market-analysis.sh。
if command -v claude >/dev/null 2>&1 || [ -x /usr/local/bin/claude ]; then
  bash "$APP_DIR/deploy/install-market-analysis.sh" --skip-cli-install || \
    echo "⚠ 市场研判服务同步失败，经营看板继续部署；请单独检查 install-market-analysis.sh"
else
  echo "⚠ 尚未安装 Claude Code CLI；市场研判页面可用，但定时研究尚未启用"
fi

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"
nginx -t && systemctl restart nginx
trap - ERR
APP_VERSION=$(grep -oP 'v\d+\.\d+\.\d+' "$APP_DIR/经营分析模板.html" | head -1 || true)

echo ""
echo "============================================"
echo "  部署完成"
echo "  访问地址: http://<服务器IP>/"
echo "  版本: ${APP_VERSION:-unknown}"
echo ""
echo "  自动部署: 已因安全整改暂停；请使用可信发布包手工执行 deploy/deploy.sh"
echo "============================================"
echo "  默认管理员账号: admin"
