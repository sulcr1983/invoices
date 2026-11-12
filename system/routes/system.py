import os
from pathlib import Path
from flask import Blueprint, request, send_from_directory, send_file

from .shared import db_manager, api_error, LOG_PATH, ARCHIVE_DIR, PROJECT_ROOT

system_bp = Blueprint('system', __name__)


def _find_archived_file(record):
    """按发票号在归档目录里精确定位原件。

    优先用「年/月」缩小范围，且要求文件名以 _<发票号> 结尾，
    避免 1234 命中 12345 这类子串误判，也避免每次 rglob 全盘扫描。
    """
    invoice_num = (record or {}).get('invoice_num') or ''
    if not invoice_num:
        return None
    archive_root = Path(str(ARCHIVE_DIR))
    if not archive_root.exists():
        return None

    candidates = []
    date_str = (record.get('date') or '')[:10]
    if len(date_str) >= 7 and date_str[4] == '-':
        year, month = date_str[:4], date_str[5:7]
        month_dir = archive_root / year / month
        if month_dir.exists():
            candidates.extend(month_dir.iterdir())
    if not candidates:
        # 兜底：只在该发票年份目录里找，仍不做全盘 rglob
        year_dirs = [d for d in archive_root.iterdir() if d.is_dir()]
        for yd in year_dirs:
            for md in yd.iterdir():
                if md.is_dir():
                    candidates.extend(md.iterdir())

    for fp in candidates:
        if fp.is_file() and fp.stem.endswith('_' + invoice_num):
            return str(fp)
    return None


@system_bp.route('/api/system/logs', methods=['GET'])
def get_system_logs():
    try:
        count = int(request.args.get('count', 100))
        level = request.args.get('level', '')
        log_path = Path(str(LOG_PATH))

        if not log_path.exists():
            # 文件不存在要说清楚（多半是日志未初始化或被清理），不能假装"没有日志"
            return {
                'status': 'success',
                'data': [],
                'warning': f'日志文件尚未生成: {log_path}'
            }

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
    """返回本地环境、数据库和目录是否可正常使用。"""
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
        data = request.get_json(silent=True) or {}
        file_md5 = data.get('md5', '')
        if not file_md5:
            return {'status': 'error', 'message': '缺少文件MD5'}, 400

        record = db_manager.get_record_by_md5(file_md5)
        if not record:
            return {'status': 'error', 'message': '未找到对应文件'}, 404

        archive_path = _find_archived_file(record)
        if not archive_path:
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

        archive_path = _find_archived_file(record)
        if not archive_path:
            return {'status': 'error', 'message': '归档文件不存在'}, 404

        return send_file(archive_path, as_attachment=False)
    except Exception as e:
        return api_error(str(e))


@system_bp.route('/api/open-dir', methods=['POST'])
def open_directory():
    """在 Windows 资源管理器中打开指定的项目文件夹。"""
    try:
        data = request.get_json(silent=True) or {}
        dir_name = data.get('dir', '')
        if not dir_name:
            return {'status': 'error', 'message': '请选择要打开的文件夹'}, 400

        allowed_dirs = {'待识别发票', '已归档发票', '识别失败待处理', '重复发票记录', 'X-处理中临时'}
        if dir_name not in allowed_dirs:
            return {'status': 'error', 'message': '没有找到这个文件夹'}, 404

        target_dir = (Path(str(PROJECT_ROOT)) / dir_name).resolve()
        project_root = Path(str(PROJECT_ROOT)).resolve()
        if project_root not in target_dir.parents:
            return {'status': 'error', 'message': '请选择系统允许打开的文件夹'}, 400

        if not target_dir.exists():
            return {'status': 'error', 'message': f'没有找到这个文件夹：{dir_name}'}, 404

        try:
            os.startfile(str(target_dir))  # Windows 打开资源管理器
        except AttributeError:
            # 非 Windows 兜底
            import webbrowser
            webbrowser.open(target_dir.as_uri())
        except OSError as e:
            return api_error(f'open_dir_error: {e}', 500)
        return {'status': 'success', 'message': f'已打开目录: {dir_name}'}
    except Exception as e:
        return api_error(str(e))


@system_bp.route('/api/webhook/config', methods=['GET'])
def get_webhook_config():
    """返回当前推送目标配置状态（只读，不暴露 URL 明文）。"""
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
    """测试企微 Webhook 是否可达（会真实发一条测试消息）。"""
    try:
        from ..config import WECOM_WEBHOOK_URL, WECOM_SCHEMA
        from ..webhook_manager import test_webhook_connection

        if not WECOM_WEBHOOK_URL:
            return {'status': 'error', 'message': 'Webhook URL 未配置'}, 400

        result = test_webhook_connection("wecom", WECOM_WEBHOOK_URL, WECOM_SCHEMA)
        return {
            'status': 'success' if result.get('ok') else 'error',
            'data': result
        }
    except Exception as e:
        return api_error(str(e))


_COMPONENTS_DIR = str(Path(__file__).resolve().parent.parent / 'components')
_ASSETS_DIR = str(Path(__file__).resolve().parent.parent / 'assets')


@system_bp.route('/assets/<path:path>')
def asset_files(path):
    """提供本地化的前端第三方资源（离线可用，不再依赖 CDN）。"""
    return send_from_directory(_ASSETS_DIR, path)


@system_bp.route('/')
def index():
    return send_from_directory(_COMPONENTS_DIR, 'index.html')


@system_bp.route('/<path:path>')
def static_files(path):
    return send_from_directory(_COMPONENTS_DIR, path)
