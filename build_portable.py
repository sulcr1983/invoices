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

PORTABLE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dist', 'portable')
RUNTIME_DIR = os.path.join(PORTABLE_DIR, 'runtime')
SITE_PKG_DIR = os.path.join(PORTABLE_DIR, 'site-packages')
APP_DIR = os.path.join(PORTABLE_DIR, 'app')
PYTHON_VERSION = '3.11.9'
PYTHON_VER_SHORT = PYTHON_VERSION.replace('.', '')[:3]
PYTHON_EMBED_URL = f'https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-embed-amd64.zip'
GET_PIP_URL = 'https://bootstrap.pypa.io/get-pip.py'
PYTHON_EXE = os.path.join(RUNTIME_DIR, 'python.exe')
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

DEPENDENCIES = [
    'Flask==3.1.0',
    'requests==2.32.3',
    'pillow==11.1.0',
    'python-dotenv==1.1.0',
    'pdfplumber==0.11.5',
    'PyMuPDF==1.25.4',
]

REMOVE_PATTERNS = [
    '__pycache__', '.dist-info', '.egg-info',
    'tests', 'testing', 'test', 'doc', 'docs',
    'examples', 'sample', 'licenses',
    '*.pyc', '*.pyo', '*.pyd',
]

REMOVE_FILES = [
    'COPYING', 'LICENSE', 'README', 'README.md', 'README.rst',
    'CHANGELOG', 'CHANGELOG.md', 'NEWS', 'NEWS.rst',
    'AUTHORS', 'CONTRIBUTING', 'CONTRIBUTING.md',
    'Makefile', 'setup.cfg', 'pyproject.toml', 'setup.py',
    'tox.ini', 'pytest.ini', '.coveragerc',
]

REMOVE_DIRS_IN_SITE = [
    os.path.join('pymupdf', 'mupdf-devel'),
    os.path.join('pymupdf', 'docs'),
    os.path.join('pymupdf', 'samples'),
    'bin',
    'pip', 'pip-*.dist-info',
    'setuptools', 'setuptools-*.dist-info',
    'wheel', 'wheel-*.dist-info',
]


def step1_download_python_embed():
    print('\n' + '='*60)
    print('步骤 1/8: 下载 Python Embeddable Package')
    print('='*60)
    os.makedirs(os.path.join(PROJECT_ROOT, 'dist'), exist_ok=True)
    embed_zip = os.path.join(PROJECT_ROOT, 'dist', 'python-embed.zip')
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
    print('步骤 2/8: 配置 Python 运行时')
    print('='*60)
    pth_file = os.path.join(RUNTIME_DIR, f'python{PYTHON_VER_SHORT}._pth')
    pth_content = f"""python{PYTHON_VER_SHORT}.zip
.
..
..\\site-packages

import site
"""
    with open(pth_file, 'w', encoding='utf-8') as f:
        f.write(pth_content)
    print(f'  已配置: {pth_file}')

    os.makedirs(SITE_PKG_DIR, exist_ok=True)
    print(f'  已创建: {SITE_PKG_DIR}')


def step3_install_pip():
    print('\n' + '='*60)
    print('步骤 3/8: 安装 pip')
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
    print('步骤 4/8: 安装项目依赖')
    print('='*60)
    subprocess.run(
        [PYTHON_EXE, '-m', 'pip', 'install'] + DEPENDENCIES +
        ['--target', SITE_PKG_DIR, '--no-warn-script-location'],
        check=True
    )
    print('  所有依赖安装完成')


def step5_copy_app():
    print('\n' + '='*60)
    print('步骤 5/8: 复制应用代码')
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

    env_file = os.path.join(PROJECT_ROOT, '.env')
    env_example = os.path.join(PROJECT_ROOT, '.env.example')
    if os.path.exists(env_file):
        shutil.copy2(env_file, os.path.join(PORTABLE_DIR, '.env'))
        print(f'  已复制: .env (含当前配置)')
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
    print('步骤 6/8: 创建启动器')
    print('='*60)

    launcher_py = os.path.join(PORTABLE_DIR, 'launcher.py')
    launcher_content = '''import sys
import os
import webbrowser
import threading
import time
import subprocess

base_dir = os.path.dirname(os.path.abspath(__file__))
os.environ['INVOICE_PROJECT_ROOT'] = base_dir
sys.path.insert(0, os.path.join(base_dir, 'app'))
sys.path.insert(0, os.path.join(base_dir, 'site-packages'))
os.chdir(base_dir)

from system.config import setup_logging
setup_logging()

def kill_port_occupants(port):
    try:
        result = subprocess.run(
            ['netstat', '-ano'], capture_output=True, text=True, timeout=5
        )
        pids = set()
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 5 and f':{port}' in parts[1] and parts[3] == 'LISTENING':
                try:
                    pids.add(int(parts[4]))
                except ValueError:
                    pass
        if pids:
            print(f"检测到端口 {port} 被占用，正在释放...")
            for pid in pids:
                try:
                    subprocess.run(['taskkill', '/F', '/PID', str(pid)],
                                   capture_output=True, timeout=5)
                    print(f"  已终止进程 PID {pid}")
                except Exception:
                    pass
            time.sleep(1)
    except Exception:
        pass

def open_browser():
    time.sleep(2)
    webbrowser.open('http://localhost:5000')

kill_port_occupants(5000)
threading.Thread(target=open_browser, daemon=True).start()

from system.api_server import app
print("="*50)
print("  SuperSu 发票自动识别验真推送系统 已启动")
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
    with open(bat_file, 'w', encoding='gbk', errors='replace') as f:
        f.write(bat_content)
    print(f'  已创建: 天颐发票系统.bat')

    readme_file = os.path.join(PORTABLE_DIR, '使用说明.txt')
    readme_content = '''SuperSu 发票自动识别验真推送系统 - 绿色便携版
====================================

使用方法：
1. 解压到任意文件夹
2. 双击"天颐发票系统.bat"启动
3. 浏览器会自动打开，显示发票管理界面
4. 关闭命令行窗口即可退出系统

配置说明：
- 如需使用百度OCR识别，请编辑 .env 文件填入API密钥
- 如需企业微信推送，请在 .env 中配置 WECOM_WEBHOOK_URL
- 不配置百度OCR也可使用，系统会自动使用PDF文本提取模式

支持格式：
- PDF 发票
- OFD 发票
- JPG/PNG 图片发票

注意事项：
- 首次启动可能需要几秒钟
- 请勿删除 runtime 文件夹和 site-packages 文件夹
- 数据库文件保存在 app/system/data/ 目录下
- 发票文件请放入"待识别发票"文件夹
'''
    with open(readme_file, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    print(f'  已创建: 使用说明.txt')


def step7_cleanup():
    print('\n' + '='*60)
    print('步骤 7/8: 清理冗余文件(减小体积)')
    print('='*60)

    removed_count = 0
    removed_size = 0

    for f in ['get-pip.py']:
        fp = os.path.join(RUNTIME_DIR, f)
        if os.path.exists(fp):
            os.remove(fp)

    for root, dirs, files in os.walk(SITE_PKG_DIR, topdown=False):
        for d in dirs:
            if d == '__pycache__' or d.endswith('.egg-info'):
                dp = os.path.join(root, d)
                s = sum(os.path.getsize(os.path.join(p, f_))
                        for p, _, fs in os.walk(dp) for f_ in fs) if os.path.exists(dp) else 0
                removed_size += s
                shutil.rmtree(dp, ignore_errors=True)
                removed_count += 1

        for f in files:
            if f.endswith(('.pyc', '.pyo')):
                fp = os.path.join(root, f)
                removed_size += os.path.getsize(fp)
                os.remove(fp)
                removed_count += 1
            fl = f.lower()
            if any(fl.startswith(rf.lower()) or fl == rf.lower() for rf in REMOVE_FILES):
                fp = os.path.join(root, f)
                if os.path.exists(fp):
                    removed_size += os.path.getsize(fp)
                    os.remove(fp)
                    removed_count += 1

        for d in dirs:
            dl = d.lower()
            if dl in ('tests', 'testing', 'test', 'doc', 'docs', 'examples', 'sample', 'licenses'):
                dp = os.path.join(root, d)
                if os.path.exists(dp) and 'flask' not in dp.lower():
                    s = sum(os.path.getsize(os.path.join(p, f_))
                            for p, _, fs in os.walk(dp) for f_ in fs)
                    removed_size += s
                    shutil.rmtree(dp, ignore_errors=True)
                    removed_count += 1

    for rm_pattern in REMOVE_DIRS_IN_SITE:
        import glob
        matches = glob.glob(os.path.join(SITE_PKG_DIR, rm_pattern))
        for rm in matches:
            if os.path.exists(rm):
                s = sum(os.path.getsize(os.path.join(p, f_))
                        for p, _, fs in os.walk(rm) for f_ in fs)
                removed_size += s
                shutil.rmtree(rm, ignore_errors=True)
                removed_count += 1

    print(f'  已清理 {removed_count} 项，释放 {removed_size/(1024*1024):.1f} MB')


def step8_report():
    print('\n' + '='*60)
    print('步骤 8/8: 统计与报告')
    print('='*60)

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
    print('SuperSu 发票自动识别验真推送系统 - 绿色便携版打包工具')
    print('='*60)
    step1_download_python_embed()
    step2_configure_python()
    step3_install_pip()
    step4_install_dependencies()
    step5_copy_app()
    step6_create_launcher()
    step7_cleanup()
    step8_report()
    print('\n' + '='*60)
    print('打包完成！')
    print(f'绿色版目录: {PORTABLE_DIR}')
    print('双击 天颐发票系统.bat 即可启动')
    print('='*60)
