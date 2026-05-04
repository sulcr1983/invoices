@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   天颐发票处理系统
echo ========================================
echo.

echo [1/4] 检查Python环境...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 错误：未找到Python，请安装 Python 3.8 或更高版本
    echo    下载地址：https://www.python.org/downloads/
    pause
    exit /b 1
)
echo    Python 环境正常

echo [2/4] 检查依赖...
pip list 2>nul | findstr "Flask" >nul
if %errorlevel% neq 0 (
    echo    正在自动安装依赖（首次运行）...
    pip install -r system/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    echo    依赖安装完成
) else (
    echo    依赖已就绪
)

echo [3/4] 检查数据目录...
if not exist "待识别发票" md "待识别发票"
if not exist "已归档发票" md "已归档发票"
if not exist "识别失败待处理" md "识别失败待处理"
if not exist "重复发票记录" md "重复发票记录"
if not exist "X-处理中临时" md "X-处理中临时"
echo    目录检查完成

echo [4/4] 启动系统...
echo.
echo ========================================
echo   系统已启动！
echo   请在浏览器中访问：http://localhost:5000
echo   按 Ctrl+C 停止服务器
echo ========================================
echo.

start http://localhost:5000
python system/api_server.py

pause
