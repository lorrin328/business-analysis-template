#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/business-analysis}"
SERVICE_NAME="${SERVICE_NAME:-business-analysis}"
RUN_USER="${RUN_USER:-www-data}"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-/opt/business-analysis-backups}"

if [ "$(id -u)" -ne 0 ]; then
  echo "请使用 sudo 运行 deploy/deploy.sh"
  exit 1
fi

apt-get update
apt-get install -y python3 python3-venv python3-pip nginx rsync

mkdir -p "$APP_DIR" "$BACKUP_DIR"
if [ -f "$APP_DIR/business_data.db" ]; then
  cp "$APP_DIR/business_data.db" "$BACKUP_DIR/business_data.db.$(date +%Y%m%d_%H%M%S)"
fi

rsync -a --delete \
  --exclude='.git' \
  --exclude='node_modules' \
  --exclude='backend/__pycache__' \
  --exclude='backend/logs/*.log' \
  --exclude='*.xlsx' \
  "$SRC_DIR/" "$APP_DIR/"

python3 -m venv "$APP_DIR/backend/venv"
"$APP_DIR/backend/venv/bin/pip" install --upgrade pip
"$APP_DIR/backend/venv/bin/pip" install -r "$APP_DIR/backend/requirements.txt"

cd "$APP_DIR/backend"
"$APP_DIR/backend/venv/bin/python" -c "from database import init_db; init_db()"

# 重建数据库（如果存在 Excel 文件）
EXCEL_COUNT=$(find "$APP_DIR" -maxdepth 1 -name "*.xlsx" 2>/dev/null | wc -l)
if [ "$EXCEL_COUNT" -ge 3 ]; then
  echo "检测到 $EXCEL_COUNT 个 Excel 文件，正在重建数据库..."
  "$APP_DIR/backend/venv/bin/python" "$APP_DIR/backend/rebuild_from_excels.py" || echo "⚠ 数据库重建失败，请手动运行 rebuild_from_excels.py"
else
  echo "⚠ 未检测到足够 Excel 文件（需 ≥3），跳过数据库重建"
  echo "  请上传 Excel 后通过 Web 界面导入，或手动运行 rebuild_from_excels.py"
fi

cp "$APP_DIR/deploy/systemd.service" "/etc/systemd/system/${SERVICE_NAME}.service"
cp "$APP_DIR/deploy/nginx.conf" /etc/nginx/sites-available/business-analysis
ln -sf /etc/nginx/sites-available/business-analysis /etc/nginx/sites-enabled/business-analysis
rm -f /etc/nginx/sites-enabled/default

# 验证 nginx 配置（client_max_body_size 必须包含）
if ! grep -q "client_max_body_size" /etc/nginx/sites-available/business-analysis; then
  echo "⚠ 警告：nginx 配置缺少 client_max_body_size，大文件上传将被拒绝（413 错误）"
fi

mkdir -p "$APP_DIR/backend/logs"
chown -R "$RUN_USER:$RUN_USER" "$APP_DIR"

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"
nginx -t && systemctl restart nginx

echo ""
echo "============================================"
echo "  部署完成"
echo "  访问地址: http://<服务器IP>/"
echo "  版本: $(grep -oP 'v\d+\.\d+\.\d+' "$APP_DIR/经营分析模板.html" | head -1)"
echo "============================================"
