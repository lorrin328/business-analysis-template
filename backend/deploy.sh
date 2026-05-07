#!/bin/bash
set -e

echo "=== 经营分析看板部署脚本 ==="

# 配置
APP_DIR="/opt/business-analysis"
SERVICE_NAME="business-analysis"
USER="www-data"

# 1. 安装依赖
echo "[1/5] 安装系统依赖..."
apt-get update
apt-get install -y python3 python3-pip python3-venv nginx

# 2. 创建应用目录
echo "[2/5] 创建应用目录..."
mkdir -p "$APP_DIR"
cp -r ../* "$APP_DIR/" || true
chown -R "$USER:$USER" "$APP_DIR"

# 3. 创建虚拟环境并安装Python依赖
echo "[3/5] 安装Python依赖..."
cd "$APP_DIR/backend"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 4. 初始化数据库
echo "[4/5] 初始化SQLite数据库..."
python3 -c "from database import init_db; init_db(); print('Database initialized')"

# 5. 创建systemd服务
echo "[5/5] 创建systemd服务..."
cat > /etc/systemd/system/$SERVICE_NAME.service << 'EOF'
[Unit]
Description=Business Analysis Dashboard API
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/business-analysis/backend
Environment="PATH=/opt/business-analysis/backend/venv/bin"
ExecStart=/opt/business-analysis/backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# 配置nginx（可选，如果需要80端口访问）
if [ ! -f /etc/nginx/sites-available/business-analysis ]; then
cat > /etc/nginx/sites-available/business-analysis << 'EOF'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
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
echo "API地址: http://<服务器IP>:8000"
echo "看板地址: http://<服务器IP>:8000/"
echo ""
echo "常用命令:"
echo "  查看状态: sudo systemctl status $SERVICE_NAME"
echo "  查看日志: sudo journalctl -u $SERVICE_NAME -f"
echo "  重启服务: sudo systemctl restart $SERVICE_NAME"
