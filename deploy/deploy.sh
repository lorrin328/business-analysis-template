#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/business-analysis}"
SERVICE_NAME="${SERVICE_NAME:-business-analysis}"
RUN_USER="${RUN_USER:-www-data}"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-/opt/business-analysis-backups}"
DB_PATH="${BUSINESS_ANALYSIS_DB:-$APP_DIR/backend/business_data.db}"

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

mkdir -p "$APP_DIR" "$BACKUP_DIR"
# 只要生产数据库存在就备份，避免有经营数据/权限数据但目标配置为空时漏备份。
if [ -f "$DB_PATH" ]; then
  BACKUP_TS="$(date +%Y%m%d_%H%M%S)"
  BACKUP_FILE="$BACKUP_DIR/business_data.db.$BACKUP_TS"
  cp "$DB_PATH" "$BACKUP_FILE"
  python3 - <<PY > "$BACKUP_FILE.meta" 2>/dev/null || true
import hashlib
import os
import sqlite3

db = "$DB_PATH"
backup = "$BACKUP_FILE"
print(f"backup_file={backup}")
print(f"source_db={db}")
print(f"size_bytes={os.path.getsize(backup)}")
try:
    with open(backup, "rb") as f:
        print("sha256=" + hashlib.sha256(f.read()).hexdigest())
    c = sqlite3.connect(backup)
    tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    print(f"table_count={len(tables)}")
    for table in ["target_config", "users", "data_imports", "agg_performance", "agg_jingdai"]:
        if table in tables:
            count = c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"{table}_count={count}")
    periods = []
    for table in ["agg_daily_performance", "agg_jingdai_daily", "agg_performance", "agg_jingdai"]:
        if table in tables:
            row = c.execute(f"SELECT MAX(year * 100 + month) FROM {table}").fetchone()
            if row and row[0]:
                periods.append(int(row[0]))
    print(f"latest_period={max(periods) if periods else ''}")
except Exception as exc:
    print(f"meta_error={exc}")
PY
  echo "已备份数据库: $BACKUP_FILE"
fi

rsync -a --delete \
  --exclude='.git' \
  --exclude='node_modules' \
  --exclude='backend/__pycache__' \
  --exclude='backend/venv' \
  --exclude='backend/logs/*.log' \
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

# 重建数据库（如果存在 Excel 文件）
EXCEL_COUNT=$(find "$APP_DIR" -maxdepth 1 -name "*.xlsx" 2>/dev/null | wc -l)
if [ "$EXCEL_COUNT" -ge 3 ]; then
  echo "检测到 $EXCEL_COUNT 个 Excel 文件，正在重建数据库..."
  "$APP_DIR/backend/venv/bin/python" "$APP_DIR/backend/rebuild_from_excels.py" || {
    echo "ERROR: 数据库重建失败，部署已中止。请检查 Excel 文件名、字段和重建日志。"
    exit 1
  }
else
  echo "⚠ 未检测到足够 Excel 文件（需 ≥3），跳过数据库重建"
  echo "  尝试从 SQLite 原始明细表重建聚合..."
  "$APP_DIR/backend/venv/bin/python" "$APP_DIR/backend/rebuild_aggregates_from_raw_tables.py" \
    || echo "⚠ SQLite 原始表重建失败；请上传 Excel 后通过 Web 界面导入，或手动运行 rebuild_from_excels.py"
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

# 自动部署 Webhook（首次安装，后续更新保留配置）
if [ ! -f /etc/systemd/system/webhook-deploy.service ]; then
  cp "$APP_DIR/deploy/webhook.service" /etc/systemd/system/webhook-deploy.service
  systemctl daemon-reload
  systemctl enable webhook-deploy
fi
if [ ! -f /etc/sudoers.d/webhook-deploy ]; then
  echo "$RUN_USER ALL=(ALL) NOPASSWD: /usr/bin/env bash $APP_DIR/deploy/deploy.sh" > /etc/sudoers.d/webhook-deploy
  chmod 440 /etc/sudoers.d/webhook-deploy
fi
if [ ! -f "$APP_DIR/deploy/.webhook_env" ]; then
  echo "⚠ 未配置 webhook 密钥，自动部署功能不可用"
  echo "  请执行: echo 'WEBHOOK_SECRET=你的密钥' > $APP_DIR/deploy/.webhook_env"
else
  systemctl restart webhook-deploy 2>/dev/null || echo "⚠ webhook-deploy 服务未启动，请检查 webhook 密钥和服务日志"
fi

mkdir -p "$APP_DIR/backend/logs"
chown -R "$RUN_USER:$RUN_USER" "$APP_DIR"

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"
nginx -t && systemctl restart nginx
APP_VERSION=$(grep -oP 'v\d+\.\d+\.\d+' "$APP_DIR/经营分析模板.html" | head -1 || true)

echo ""
echo "============================================"
echo "  部署完成"
echo "  访问地址: http://<服务器IP>/"
echo "  版本: ${APP_VERSION:-unknown}"
echo ""
echo "  自动部署:"
echo "    1. 在 GitHub Settings → Webhooks 添加:"
echo "       URL: http://<服务器IP>/webhook/deploy"
echo "       Secret: 与服务器 $APP_DIR/deploy/.webhook_env 一致"
echo "    2. 验证: systemctl status webhook-deploy"
echo "============================================"
echo "  默认管理员账号: admin"
