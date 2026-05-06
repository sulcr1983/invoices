"""
天颐发票处理系统 - 绿色便携版打包脚本
使用 Python Embeddable Package 制作免安装绿色版
"""
import os
import sys
import shutil
import subprocess
import zipfile
import urllib.request

PORTABLE_DIR = os.path.join(os.path.dirname(__file__), 'dist', 'portable')
RUNTIME_DIR = os.path.join(PORTABLE_DIR, 'runtime')
SITE_PKG_DIR = os.path.join(PORTABLE_DIR, 'site-packages')
APP_DIR = os.path.join(PORTABLE_DIR, 'app')
PYTHON_VERSION = '3.12.2'
PYTHON_VER_SHORT = PYTHON_VERSION.replace('.', '')[:2]
PYTHON_EMBED_URL = f'https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-embed-amd64.zip'
GET_PIP_URL = 'https://bootstrap.pypa.io/get-pip.py'
PYTHON_EXE = os.path.join(RUNTIME_DIR, 'python.exe')
PROJECT_ROOT = os.path.dirname(__file__)

DEPENDENCIES = [
    'Flask==3.1.0',
    'requests==2.32.3',
    'pillow==11.1.0',
    'python-dotenv==1.1.0',
    'pdfplumber==0.11.5',
    'PyMuPDF==1.25.4',
]


def step1_download_python_embed():
    print('\n' + '='*60)
    print('步骤 1/7: 下载 Python Embeddable Package')
    print('='*60)
    os.makedirs(os.path.join(os.path.dirname(__file__), 'dist'), exist_ok=True)
    embed_zip = os.path.join(os.path.dirname(__file__), 'dist', 'python-embed.zip')
    if not os.path.exists(embed_zip):
        print(f'  下载中: {PYTHON_EMBED_URL}')
        urllib.request.urlretrieve(PYTHON_EMBED_URL, embed_zip)
        print(f'  已下载: {embed_zip}')
    else:
        print(f'  已存在: {embed_zip}')

    if not os.path.exists(os.path.join(RUNTIME_DIR, 'python.exe')):
        os.makedirs(RUNTIME_DIR, exist_ok=True)
        with zipfile.ZipFile(embed_zip, 'r') as z:
            z.extractall(RUNTIME_DIR)
        print(f'  已解压到: {RUNTIME_DIR}')
    else:
        print(f'  已存在: {RUNTIME_DIR}')


def step2_configure_python():
    print('\n' + '='*60)
    print('步骤 2/7: 配置 Python 运行时')
    print('='*60)
    pth_file = os.path.join(RUNTIME_DIR, f'python{PYTHON_VER_SHORT}._pth')
    pth_content = f"""python{PYTHON_VER_SHORT}.zip
.
..

import site
"""
    with open(pth_file, 'w', encoding='utf-8') as f:
        f.write(pth_content)
    print(f'  已配置: {pth_file}')

    os.makedirs(SITE_PKG_DIR, exist_ok=True)
    print(f'  已创建: {SITE_PKG_DIR}')


def step3_install_pip():
    print('\n' + '='*60)
    print('步骤 3/7: 安装 pip')
    print('='*60)
    get_pip = os.path.join(RUNTIME_DIR, 'get-pip.py')
    if not os.path.exists(get_pip):
        print(f'  下载中: {GET_PIP_URL}')
        urllib.request.urlretrieve(GET_PIP_URL, get_pip)
    subprocess.run([PYTHON_EXE, get_pip, '--no-warn-script-location'],
                   check=True, capture_output=True)
    print('  pip 安装完成')


def step4_install_dependencies():
    print('\n' + '='*60)
    print('步骤 4/7: 安装项目依赖')
    print('='*60)
    subprocess.run(
        [PYTHON_EXE, '-m', 'pip', 'install'] + DEPENDENCIES +
        ['--target', SITE_PKG_DIR, '--no-warn-script-location'],
        check=True, capture_output=True
    )
    print('  所有依赖安装完成')


def step5_copy_app():
    print('\n' + '='*60)
    print('步骤 5/7: 复制应用代码')
    print('='*60)
    if os.path.exists(APP_DIR):
        shutil.rmtree(APP_DIR)

    system_src = os.path.join(PROJECT_ROOT, 'system')
    system_dst = os.path.join(APP_DIR, 'system')

    ignore_patterns = shutil.ignore_patterns(
        '__pycache__', '*.pyc', '*.pyo', '.pytest_cache',
        'tests', 'tech_debt.md', 'data'
    )
    shutil.copytree(system_src, system_dst, ignore=ignore_patterns)
    print(f'  已复制: system/ -> app/system/')

    env_example = os.path.join(PROJECT_ROOT, '.env.example')
    if os.path.exists(env_example):
        shutil.copy2(env_example, os.path.join(PORTABLE_DIR, '.env.example'))
        print(f'  已复制: .env.example')

    dirs_to_create = ['待识别发票', 'X-处理中临时', '已归档发票', '识别失败待处理', '重复发票记录']
    for d in dirs_to_create:
        dp = os.path.join(PORTABLE_DIR, d)
        os.makedirs(dp, exist_ok=True)
    print(f'  已创建业务目录')


def step6_create_launcher():
    print('\n' + '='*60)
    print('步骤 6/7: 创建启动器')
    print('='*60)

    launcher_py = os.path.join(PORTABLE_DIR, 'launcher.py')
    launcher_content = '''import sys
import os
import webbrowser
import threading
import time

base_dir = os.path.dirname(os.path.abspath(__file__))
os.environ['INVOICE_PROJECT_ROOT'] = base_dir
sys.path.insert(0, os.path.join(base_dir, 'app'))
sys.path.insert(0, os.path.join(base_dir, 'site-packages'))
os.chdir(base_dir)

from system.config import setup_logging
setup_logging()

def open_browser():
    time.sleep(2)
    webbrowser.open('http://localhost:5000')

threading.Thread(target=open_browser, daemon=True).start()

from system.api_server import app
print("="*50)
print("  天颐发票处理系统 已启动")
print("  浏览器将自动打开 http://localhost:5000")
print("  关闭此窗口即可退出系统")
print("="*50)
app.run(host='127.0.0.1', port=5000, debug=False)
'''
    with open(launcher_py, 'w', encoding='utf-8') as f:
        f.write(launcher_content)
    print(f'  已创建: launcher.py')

    bat_file = os.path.join(PORTABLE_DIR, '天颐发票系统.bat')
    bat_content = '''@echo off
chcp 65001 >nul 2>&1
title 天颐发票处理系统
cd /d "%~dp0"
runtime\\python.exe launcher.py
if errorlevel 1 (
    echo.
    echo 程序运行出错，请检查配置文件 .env
    pause
)
'''
    with open(bat_file, 'w', encoding='utf-8') as f:
        f.write(bat_content)
    print(f'  已创建: 天颐发票系统.bat')

    readme_file = os.path.join(PORTABLE_DIR, '使用说明.txt')
    readme_content = '''天颐发票处理系统 - 绿色便携版
====================================

使用方法：
1. 解压到任意文件夹
2. 双击"天颐发票系统.bat"启动
3. 浏览器会自动打开，显示发票管理界面
4. 关闭命令行窗口即可退出系统

配置说明：
- 如需使用百度OCR识别，请复制 .env.example 为 .env 并填入API密钥
- 不配置百度OCR也可使用，系统会自动使用PDF文本提取模式

支持格式：
- PDF 发票
- OFD 发票
- JPG/PNG 图片发票

注意事项：
- 首次启动可能需要几秒钟
- 请勿删除 runtime 文件夹和 site-packages 文件夹
- 数据库文件保存在 app/system/data/ 目录下
'''
    with open(readme_file, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    print(f'  已创建: 使用说明.txt')


def step7_cleanup_and_report():
    print('\n' + '='*60)
    print('步骤 7/7: 清理与统计')
    print('='*60)

    for f in ['get-pip.py']:
        fp = os.path.join(RUNTIME_DIR, f)
        if os.path.exists(fp):
            os.remove(fp)
            print(f'  已删除: {f}')

    for root, dirs, files in os.walk(SITE_PKG_DIR, topdown=False):
        for d in dirs:
            if d == '__pycache__':
                shutil.rmtree(os.path.join(root, d))

    for rm in [os.path.join(SITE_PKG_DIR, 'pymupdf', 'mupdf-devel'),
               os.path.join(SITE_PKG_DIR, 'bin')]:
        if os.path.exists(rm):
            shutil.rmtree(rm)
            print(f'  已删除: {os.path.basename(rm)}')

    total_size = 0
    for root, dirs, files in os.walk(PORTABLE_DIR):
        for f in files:
            fp = os.path.join(root, f)
            total_size += os.path.getsize(fp)

    mb = total_size / (1024 * 1024)
    print(f'\n  打包目录: {PORTABLE_DIR}')
    print(f'  总大小: {mb:.1f} MB')
    print(f'  预计7z压缩后: ~{mb*0.35:.0f} MB')
    print(f'\n  目录结构:')
    for item in sorted(os.listdir(PORTABLE_DIR)):
        ip = os.path.join(PORTABLE_DIR, item)
        if os.path.isdir(ip):
            size = sum(os.path.getsize(os.path.join(dp, f))
                       for dp, _, fns in os.walk(ip) for f in fns)
            print(f'    {item}/ ({size/(1024*1024):.1f} MB)')
        else:
            size = os.path.getsize(ip)
            print(f'    {item} ({size/1024:.0f} KB)')


if __name__ == '__main__':
    print('天颐发票处理系统 - 绿色便携版打包工具')
    print('='*60)
    step1_download_python_embed()
    step2_configure_python()
    step3_install_pip()
    step4_install_dependencies()
    step5_copy_app()
    step6_create_launcher()
    step7_cleanup_and_report()
    print('\n' + '='*60)
    print('打包完成！')
    print(f'绿色版目录: {PORTABLE_DIR}')
    print('双击 天颐发票系统.bat 即可启动')
    print('='*60)
