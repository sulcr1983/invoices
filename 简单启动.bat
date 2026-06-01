@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo ========================================
echo   天颐发票处理系统
echo ========================================
echo.

echo [1/4] 检查Python环境...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误]: 未找到Python，请安装 Python 3.8 或更高版本
    echo    下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=2" %%i in ('python --version 2^>^&1') do echo   Python %%i OK

echo [2/4] 检查依赖...
pip list 2>nul | findstr /i "Flask" >nul
if %errorlevel% neq 0 (
    echo    正在自动安装依赖(首次运行)...
    pip install -r system/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    echo    依赖安装完成
) else (
    echo    依赖已就绪
)

echo [3/4] 检查工作目录...
for %%d in ("待识别发票" "已归档发票" "识别失败待处理" "重复发票记录" "X-处理中临时") do (
    if not exist "%%~d" md "%%~d" >nul 2>&1
)
echo    目录检查完毕

echo [4/4] 检查端口并启动系统...
netstat -ano | findstr ":5000.*LISTENING" >nul 2>&1
if %errorlevel% equ 0 (
    echo    检测到端口5000被占用，正在释放...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5000.*LISTENING"') do (
        taskkill /F /PID %%a >nul 2>&1
        echo    已终止PID: %%a
    )
    timeout /t 1 /nobreak >nul
    echo    端口已释放
)

echo.
echo ========================================
echo   系统启动中!
echo   访问地址: http://localhost:5000
echo   按 Ctrl+C 停止服务器
echo ========================================
echo.

start http://localhost:5000
python system/api_server.py

pause
