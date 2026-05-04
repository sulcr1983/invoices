import subprocess
from pathlib import Path
from flask import Blueprint, request, send_from_directory, send_file

from .shared import db_manager, api_error, LOG_PATH, ARCHIVE_DIR, PROJECT_ROOT

system_bp = Blueprint('system', __name__)


@system_bp.route('/api/system/logs', methods=['GET'])
def get_system_logs():
    try:
        count = int(request.args.get('count', 100))
        level = request.args.get('level', '')
        log_path = Path(str(LOG_PATH))

        if not log_path.exists():
            return {'status': 'success', 'data': []}

        entries = []
        with open(str(log_path), 'r', encoding='utf-8') as lf:
            lines = lf.readlines()
            for line in lines[-count:]:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(' / ')
                ts = ''
                lvl = 'info'
                src = ''
                msg = line
                if len(parts) >= 4:
                    ts = parts[0]
                    lvl = parts[1]
                    src = parts[2]
                    msg = ' / '.join(parts[3:])

                if level and lvl.lower() != level.lower():
                    continue
                entries.append({'timestamp': ts, 'level': lvl.lower(), 'source': src, 'message': msg})

        return {'status': 'success', 'data': entries}
    except Exception as e:
        return api_error(str(e))


@system_bp.route('/api/system/status', methods=['GET'])
def get_system_status():
    try:
        try:
            from ..core.pipeline import check_environment
            from ..services import ensure_directories
        except ImportError:
            from core.pipeline import check_environment
            from services import ensure_directories
        env_ok = check_environment()
        db_ok = True
        try:
            db_manager.get_stats()
        except Exception:
            db_ok = False
        dir_ok = True
        try:
            ensure_directories()
        except Exception:
            dir_ok = False

        return {
            'status': 'success',
            'data': {'environment': env_ok, 'database': db_ok, 'directories': dir_ok}
        }
    except Exception as e:
        return api_error(str(e))


@system_bp.route('/api/invoice/original', methods=['POST'])
def view_original_invoice():
    try:
        data = request.get_json()
        file_md5 = data.get('md5', '')
        if not file_md5:
            return {'status': 'error', 'message': '缺少文件MD5'}, 400

        record = db_manager.get_record_by_md5(file_md5)
        if not record:
            return {'status': 'error', 'message': '未找到对应文件'}, 404

        try:
            from ..core.data_utils import calculate_file_md5
        except ImportError:
            from core.data_utils import calculate_file_md5

        archive_dir = Path(str(ARCHIVE_DIR))
        archive_path = None
        for fpath in archive_dir.rglob('*'):
            if fpath.is_file() and calculate_file_md5(str(fpath)) == file_md5:
                archive_path = str(fpath)
                break

        if not archive_path or not Path(archive_path).exists():
            return {'status': 'error', 'message': '归档文件不存在'}, 404

        return {
            'status': 'success',
            'message': '已找到归档文件',
            'path': archive_path,
            'url': f'/api/invoice/file/{file_md5}'
        }
    except Exception as e:
        return api_error(str(e))


@system_bp.route('/api/invoice/file/<file_md5>', methods=['GET'])
def serve_original_invoice(file_md5):
    try:
        try:
            from ..core.data_utils import calculate_file_md5
        except ImportError:
            from core.data_utils import calculate_file_md5

        archive_dir = Path(str(ARCHIVE_DIR))
        archive_path = None
        for fpath in archive_dir.rglob('*'):
            if fpath.is_file() and calculate_file_md5(str(fpath)) == file_md5:
                archive_path = str(fpath)
                break

        if not archive_path or not Path(archive_path).exists():
            return {'status': 'error', 'message': '归档文件不存在'}, 404

        return send_file(archive_path, as_attachment=False)
    except Exception as e:
        return api_error(str(e))


@system_bp.route('/api/open-dir', methods=['POST'])
def open_directory():
    try:
        data = request.get_json()
        dir_name = data.get('dir', '')
        if not dir_name:
            return {'status': 'error', 'message': '缺少目录名称'}, 400

        target_dir = Path(str(PROJECT_ROOT)) / dir_name

        if not target_dir.exists():
            return {'status': 'error', 'message': f'目录不存在: {dir_name}'}, 404

        subprocess.Popen(['explorer', str(target_dir)])
        return {'status': 'success', 'message': f'已打开目录: {dir_name}'}
    except Exception as e:
        return api_error(str(e))


@system_bp.route('/')
def index():
    return send_from_directory('components', 'index.html')


@system_bp.route('/<path:path>')
def static_files(path):
    return send_from_directory('components', path)
