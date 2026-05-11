#!/bin/bash
set -e

echo "=== 经营分析看板部署脚本 ==="
echo ""

# 配置
APP_DIR="/opt/business-analysis"
SERVICE_NAME="business-analysis"
BACKUP_DIR="/opt/business-analysis-backups"
USER="www-data"

# 获取脚本所在目录（项目根目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[0/6] 检查环境..."
if [ "$EUID" -ne 0 ]; then
    echo "[错误] 请使用 sudo 运行此脚本"
    exit 1
fi

# 1. 安装依赖
echo "[1/6] 安装系统依赖..."
apt-get update > /dev/null
apt-get install -y python3 python3-pip python3-venv nginx rsync > /dev/null

# 2. 备份现有数据（如果存在）
if [ -f "$APP_DIR/backend/business_data.db" ]; then
    echo "[2/6] 备份现有数据库..."
    mkdir -p "$BACKUP_DIR"
    BACKUP_FILE="$BACKUP_DIR/business_data.db.$(date +%Y%m%d_%H%M%S)"
    cp "$APP_DIR/backend/business_data.db" "$BACKUP_FILE"
    echo "      已备份到: $BACKUP_FILE"
else
    echo "[2/6] 无需备份（首次部署）"
fi

# 3. 创建应用目录并同步文件（排除开发文件）
echo "[3/6] 同步应用文件..."
mkdir -p "$APP_DIR"

# 使用 rsync 排除不需要的文件
rsync -a --delete \
    --exclude='venv' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.git' \
    --exclude='.gitignore' \
    --exclude='node_modules' \
    --exclude='*.md' \
    --exclude='docs' \
    --exclude='js' \
    --exclude='build.sh' \
    --exclude='CHANGELOG.md' \
    --exclude='需求文档.md' \
    --exclude='backend/venv' \
    --exclude='backend/__pycache__' \
    --exclude='backend/deploy.sh' \
    --exclude='backend/start.sh' \
    --exclude='backend/start.bat' \
    "$SCRIPT_DIR/" "$APP_DIR/"

chown -R "$USER:$USER" "$APP_DIR"

# 4. 创建虚拟环境并安装Python依赖
echo "[4/6] 安装Python依赖..."
cd "$APP_DIR/backend"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip > /dev/null
pip install -r requirements.txt > /dev/null

# 5. 初始化数据库（不会覆盖已有数据）
echo "[5/6] 初始化SQLite数据库..."
python3 -c "from db import init_db; init_db(); print('Database initialized')"

# 6. 创建systemd服务
echo "[6/6] 配置systemd服务..."
cat > /etc/systemd/system/$SERVICE_NAME.service << EOF
[Unit]
Description=Business Analysis Dashboard API
After=network.target

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$APP_DIR/backend
Environment="PATH=$APP_DIR/backend/venv/bin"
ExecStart=$APP_DIR/backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 45679
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# 配置nginx（如果尚未配置）
if [ ! -f /etc/nginx/sites-available/business-analysis ]; then
    echo "      配置 Nginx..."
    cat > /etc/nginx/sites-available/business-analysis << 'EOF'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:45679;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
EOF
    ln -s /etc/nginx/sites-available/business-analysis /etc/nginx/sites-enabled/ 2>/dev/null || true
fi

# 启动服务
systemctl daemon-reload
systemctl enable $SERVICE_NAME
systemctl restart $SERVICE_NAME
systemctl restart nginx

echo ""
echo "=== 部署完成 ==="
echo "看板地址: http://<服务器IP>/"
echo ""
echo "常用命令:"
echo "  查看状态: sudo systemctl status $SERVICE_NAME"
echo "  查看日志: sudo journalctl -u $SERVICE_NAME -f"
echo "  重启服务: sudo systemctl restart $SERVICE_NAME"
echo "  数据库备份目录: $BACKUP_DIR"
echo ""
echo "如需开发环境跨域，启动时设置环境变量:"
echo "  CORS_ORIGINS=http://localhost:8080 sudo systemctl restart $SERVICE_NAME"
