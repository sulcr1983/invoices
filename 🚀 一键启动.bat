@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   SuperSu 发票处理系统
echo ========================================
echo.

echo [1/4] ���Python����...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [����]: δ�ҵ�Python���밲װ Python 3.8 ����߰汾
    echo    ���ص�ַ: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo    Python ��������

echo [2/4] �������...
pip list 2>nul | findstr "Flask" >nul
if %errorlevel% neq 0 (
    echo    �����Զ���װ����(�״�����)...
    pip install -r system/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    echo    ������װ���
) else (
    echo    �����Ѿ���
)

echo [3/4] �������Ŀ¼...
if not exist "��ʶ��Ʊ" md "��ʶ��Ʊ"
if not exist "�ѹ鵵��Ʊ" md "�ѹ鵵��Ʊ"
if not exist "ʶ��ʧ�ܴ�����" md "ʶ��ʧ�ܴ�����"
if not exist "�ظ���Ʊ��¼" md "�ظ���Ʊ��¼"
if not exist "X-��������ʱ" md "X-��������ʱ"
echo    Ŀ¼������

echo [4/4] ����ϵͳ...
echo.
echo ========================================
echo   ϵͳ������!
echo   �����: http://localhost:5000
echo   �� Ctrl+C ֹͣ������
echo ========================================
echo.

start http://localhost:5000
python system/api_server.py

pause
