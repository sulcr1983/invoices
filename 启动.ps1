# ========================================
# 天颐发票处理系统 - 启动脚本 (PowerShell)
# ========================================

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  天颐发票处理系统" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查Python环境
Write-Host "[1/4] 检查Python环境..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "   $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "[错误]: 未找到Python，请安装 Python 3.8 或更高版本" -ForegroundColor Red
    Write-Host "   下载地址: https://www.python.org/downloads/" -ForegroundColor Red
    Read-Host "按任意键退出"
    exit 1
}

# 检查依赖
Write-Host "[2/4] 检查依赖..." -ForegroundColor Yellow
$flaskInstalled = pip list 2>$null | Select-String "Flask"
if (-not $flaskInstalled) {
    Write-Host "   正在自动安装依赖(首次运行)..." -ForegroundColor Yellow
    pip install -r system/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    Write-Host "   依赖安装完成" -ForegroundColor Green
} else {
    Write-Host "   依赖已就绪" -ForegroundColor Green
}

# 检查工作目录
Write-Host "[3/4] 检查工作目录..." -ForegroundColor Yellow
$dirs = @("待识别发票", "已归档发票", "识别失败待处理", "重复发票记录", "X-处理中临时")
foreach ($dir in $dirs) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}
Write-Host "   目录检查完毕" -ForegroundColor Green

# 检查端口并启动
Write-Host "[4/4] 检查端口并启动系统..." -ForegroundColor Yellow
$portOccupied = netstat -ano | Select-String ":5000.*LISTENING"
if ($portOccupied) {
    Write-Host "   检测到端口5000被占用，正在释放..." -ForegroundColor Yellow
    $pids = $portOccupied | ForEach-Object { [int]($_ -split '\s+')[-1] }
    foreach ($pid in $pids) {
        try {
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            Write-Host "   已终止进程 PID: $pid" -ForegroundColor Gray
        } catch {}
    }
    Start-Sleep -Seconds 1
    Write-Host "   端口已释放" -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  系统启动中!" -ForegroundColor Cyan
Write-Host "  访问地址: http://localhost:5000" -ForegroundColor Cyan
Write-Host "  按 Ctrl+C 停止服务器" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 自动打开浏览器
Start-Process "http://localhost:5000"

# 启动服务器
python system/api_server.py

Read-Host "`n服务器已停止，按任意键退出"
