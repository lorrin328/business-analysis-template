@echo off
chcp 65001 >nul
echo === 经营分析看板 - 本地启动脚本 ===
echo.

set BACKEND_DIR=%~dp0
set PARENT_DIR=%BACKEND_DIR%..

cd /d "%BACKEND_DIR%"

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)

:: 检查虚拟环境
if not exist "venv\Scripts\activate.bat" (
    echo [1/3] 创建虚拟环境...
    python -m venv venv
)

:: 激活虚拟环境并安装依赖
echo [2/3] 安装依赖...
call venv\Scripts\activate.bat
pip install -q -r requirements.txt

:: 初始化数据库
echo [3/3] 初始化数据库...
python -c "from database import init_db; init_db(); print('Database initialized')"

echo.
echo === 启动服务 ===
echo 浏览器将自动打开 http://localhost:8000
echo 按 Ctrl+C 停止服务
echo.

:: 启动浏览器（延迟2秒确保服务启动）
start "" /b cmd /c "timeout /t 2 >nul && start http://localhost:8000"

:: 启动服务
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
