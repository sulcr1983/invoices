@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   天颐发票处理系统 - Web界面
echo ========================================
echo.

echo [1/3] 检查Python环境...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 错误：未找到Python，请确保已安装Python 3.8或更高版本
    pause
    exit /b 1
)

echo [2/3] 检查依赖...
pip list 2>nul | findstr "Flask" >nul
if %errorlevel% neq 0 (
    echo    正在安装依赖...
    pip install -r system/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
)

echo [3/3] 启动服务器...
echo.
echo ========================================
echo   访问地址: http://localhost:5000
echo   按 Ctrl+C 停止服务器
echo ========================================
echo.

start http://localhost:5000
python system/api_server.py

pause
