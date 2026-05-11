#!/bin/bash
set -e

echo "=== 经营分析看板 - 本地启动脚本 ==="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未找到 python3，请先安装 Python 3.10+"
    exit 1
fi

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "[1/3] 创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境并安装依赖
echo "[2/3] 安装依赖..."
source venv/bin/activate
pip install -q -r requirements.txt

# 初始化数据库
echo "[3/3] 初始化数据库..."
python3 -c "from db import init_db; init_db(); print('Database initialized')"

echo ""
echo "=== 启动服务 ==="
echo "访问地址: http://localhost:8000"
echo "按 Ctrl+C 停止服务"
echo ""

# 延迟打开浏览器
(sleep 2 && open http://localhost:8000 2>/dev/null || xdg-open http://localhost:8000 2>/dev/null || true) &

# 启动服务
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
