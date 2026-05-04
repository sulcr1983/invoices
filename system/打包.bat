@echo off
chcp 65001 >nul
echo ========================================
echo   天颐发票处理系统 - 打包脚本
echo ========================================
echo.

set ZIP_NAME=天颐发票处理系统_v1.0.zip
set SOURCE_DIR=%~dp0
set TEMP_DIR=%TEMP%\invoice_package

echo [1/5] 清理临时文件...
if exist "%TEMP_DIR%" rmdir /s /q "%TEMP_DIR%"
if exist "%ZIP_NAME%" del /f /q "%ZIP_NAME%"

echo [2/5] 复制核心文件...
mkdir "%TEMP_DIR%"
mkdir "%TEMP_DIR%\system"
mkdir "%TEMP_DIR%\system\core"
mkdir "%TEMP_DIR%\system\database"
mkdir "%TEMP_DIR%\system\services"
mkdir "%TEMP_DIR%\system\components"
mkdir "%TEMP_DIR%\system\data"
mkdir "%TEMP_DIR%\system\tests"

copy "🚀 一键启动.bat" "%TEMP_DIR%\" >nul
copy ".env.example" "%TEMP_DIR%\" >nul
copy ".gitignore" "%TEMP_DIR%\" >nul

copy "system\__init__.py" "%TEMP_DIR%\system\" >nul
copy "system\config.py" "%TEMP_DIR%\system\" >nul
copy "system\db_manager.py" "%TEMP_DIR%\system\" >nul
copy "system\extractor.py" "%TEMP_DIR%\system\" >nul
copy "system\main.py" "%TEMP_DIR%\system\" >nul
copy "system\api_server.py" "%TEMP_DIR%\system\" >nul
copy "system\webhook_manager.py" "%TEMP_DIR%\system\" >nul
copy "system\requirements.txt" "%TEMP_DIR%\system\" >nul

copy "system\core\__init__.py" "%TEMP_DIR%\system\core\" >nul
copy "system\core\baidu_ocr.py" "%TEMP_DIR%\system\core\" >nul
copy "system\core\data_utils.py" "%TEMP_DIR%\system\core\" >nul
copy "system\core\invoice_parser.py" "%TEMP_DIR%\system\core\" >nul
copy "system\core\pdf_utils.py" "%TEMP_DIR%\system\core\" >nul
copy "system\core\pipeline.py" "%TEMP_DIR%\system\core\" >nul
copy "system\core\text_invoice_parser.py" "%TEMP_DIR%\system\core\" >nul
copy "system\core\webhook_payload.py" "%TEMP_DIR%\system\core\" >nul

copy "system\database\__init__.py" "%TEMP_DIR%\system\database\" >nul
copy "system\database\connection.py" "%TEMP_DIR%\system\database\" >nul
copy "system\database\models.py" "%TEMP_DIR%\system\database\" >nul
copy "system\database\queries.py" "%TEMP_DIR%\system\database\" >nul
copy "system\database\writes.py" "%TEMP_DIR%\system\database\" >nul
copy "system\database\webhooks.py" "%TEMP_DIR%\system\database\" >nul
copy "system\database\locks.py" "%TEMP_DIR%\system\database\" >nul

copy "system\services\__init__.py" "%TEMP_DIR%\system\services\" >nul
copy "system\services\file_service.py" "%TEMP_DIR%\system\services\" >nul
copy "system\services\invoice_service.py" "%TEMP_DIR%\system\services\" >nul
copy "system\services\sync_service.py" "%TEMP_DIR%\system\services\" >nul

copy "system\components\index.html" "%TEMP_DIR%\system\components\" >nul

copy "system\data\invoices.db" "%TEMP_DIR%\system\data\" >nul

echo [3/5] 创建空目录结构...
mkdir "%TEMP_DIR%\待识别发票"
mkdir "%TEMP_DIR%\X-处理中临时"
mkdir "%TEMP_DIR%\已归档发票"
mkdir "%TEMP_DIR%\识别失败待处理"
mkdir "%TEMP_DIR%\重复发票记录"

echo. > "%TEMP_DIR%\待识别发票\.keep"
echo. > "%TEMP_DIR%\X-处理中临时\.keep"
echo. > "%TEMP_DIR%\已归档发票\.keep"
echo. > "%TEMP_DIR%\识别失败待处理\.keep"
echo. > "%TEMP_DIR%\重复发票记录\.keep"

echo [4/5] 打包ZIP...
powershell -Command "Compress-Archive -Path '%TEMP_DIR%\*' -DestinationPath '%SOURCE_DIR%%ZIP_NAME%' -Force"

echo [5/5] 清理临时文件...
rmdir /s /q "%TEMP_DIR%"

echo.
echo ========================================
echo   打包完成！
echo   文件: %ZIP_NAME%
echo   位置: %SOURCE_DIR%
echo ========================================
echo.
pause
