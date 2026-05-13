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
        from ..core.pipeline import check_environment
        from ..services import ensure_directories
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

        invoice_num = record[1] if len(record) > 1 else None
        archive_dir = Path(str(ARCHIVE_DIR))
        archive_path = None
        if invoice_num:
            for fpath in archive_dir.rglob(f'*{invoice_num}*'):
                if fpath.is_file():
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
        record = db_manager.get_record_by_md5(file_md5)
        if not record:
            return {'status': 'error', 'message': '未找到对应文件'}, 404

        invoice_num = record[1] if len(record) > 1 else None
        archive_dir = Path(str(ARCHIVE_DIR))
        archive_path = None
        if invoice_num:
            for fpath in archive_dir.rglob(f'*{invoice_num}*'):
                if fpath.is_file():
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


@system_bp.route('/api/webhook/config', methods=['GET'])
def get_webhook_config():
    try:
        from ..config import WECOM_WEBHOOK_URL, WECOM_SCHEMA
        
        has_webhook = bool(WECOM_WEBHOOK_URL)
        has_schema = bool(WECOM_SCHEMA)
        
        return {
            'status': 'success',
            'data': {
                'webhook_configured': has_webhook,
                'schema_configured': has_schema,
                'platform': 'wecom',
                'has_schema': has_schema
            }
        }
    except Exception as e:
        return api_error(str(e))


@system_bp.route('/api/webhook/test', methods=['POST'])
def test_webhook():
    try:
        from ..config import WECOM_WEBHOOK_URL, WECOM_SCHEMA
        from ..webhook_manager import test_webhook_connection
        
        if not WECOM_WEBHOOK_URL:
            return {'status': 'error', 'message': 'Webhook URL 未配置'}, 400
        
        result = test_webhook_connection("wecom", WECOM_WEBHOOK_URL, WECOM_SCHEMA)
        
        return {
            'status': 'success' if result['ok'] else 'error',
            'data': result
        }
    except Exception as e:
        return api_error(str(e))


@system_bp.route('/')
def index():
    from flask import make_response
    try:
        with open('components/index.html', 'r', encoding='utf-8') as f:
            content = f.read()
        response = make_response(content)
        response.headers['Content-Type'] = 'text/html; charset=utf-8'
        return response
    except Exception as e:
        return send_from_directory('components', 'index.html')


@system_bp.route('/<path:path>')
def static_files(path):
    from flask import make_response
    try:
        if path.endswith('.html') or path.endswith('.js') or path.endswith('.css'):
            with open(f'components/{path}', 'r', encoding='utf-8') as f:
                content = f.read()
            response = make_response(content)
            if path.endswith('.html'):
                response.headers['Content-Type'] = 'text/html; charset=utf-8'
            elif path.endswith('.js'):
                response.headers['Content-Type'] = 'application/javascript; charset=utf-8'
            elif path.endswith('.css'):
                response.headers['Content-Type'] = 'text/css; charset=utf-8'
            return response
        return send_from_directory('components', path)
    except Exception as e:
        return send_from_directory('components', path)
