import logging
import threading
from pathlib import Path
from flask import Blueprint, request

from .shared import db_manager, api_error, add_log, get_recent_logs, clear_logs, err_to_cn

tasks_bp = Blueprint('tasks', __name__)


@tasks_bp.route('/api/tasks/pending', methods=['GET'])
def get_pending_files():
    try:
        from ..services import scan_pending_files, ensure_directories
        ensure_directories()
        pending_files = scan_pending_files()
        return {
            'status': 'success',
            'data': {'files': pending_files, 'count': len(pending_files)}
        }
    except Exception as e:
        return api_error(str(e))


@tasks_bp.route('/api/upload', methods=['POST'])
def upload_files():
    try:
        from ..config import INPUT_DIR
        from ..services import ensure_directories
        ensure_directories()
        files = request.files.getlist('files')
        if not files:
            return {'status': 'error', 'message': '没有选择文件'}, 400

        uploaded = []
        skipped = []
        input_dir = Path(str(INPUT_DIR))
        for f in files:
            if f.filename == '':
                continue
            safe_name = f.filename
            dest = input_dir / safe_name
            if dest.exists():
                skipped.append(safe_name)
                continue
            f.save(str(dest))
            uploaded.append(safe_name)

        return {
            'status': 'success',
            'data': {'uploaded': uploaded, 'skipped': skipped, 'total': len(uploaded)}
        }
    except Exception as e:
        return api_error(str(e))


_pipeline_result = {'running': False, 'stats': None, 'error': None}
_pipeline_lock = threading.Lock()


def _run_pipeline_async():
    try:
        from ..core.pipeline import run_pipeline, logger as pipeline_logger
        with _pipeline_lock:
            _pipeline_result['running'] = True
            _pipeline_result['stats'] = None
            _pipeline_result['error'] = None

        class LogCaptureHandler(logging.Handler):
            def emit(self, record):
                level_map = {logging.WARNING: 'warning', logging.ERROR: 'error', logging.CRITICAL: 'error'}
                lvl = level_map.get(record.levelno, 'info')
                msg = self.format(record)
                add_log(msg, lvl)

        handler = LogCaptureHandler()
        handler.setFormatter(logging.Formatter('%(message)s'))
        pipeline_logger.addHandler(handler)

        add_log('系统就绪，等待开始处理发票...', 'info')
        add_log('开始处理发票...', 'info')

        try:
            stats, batch_id = run_pipeline()
        finally:
            pipeline_logger.removeHandler(handler)

        if stats['success'] > 0:
            add_log(f'成功识别并归档发票：{stats["success"]} 张', 'success')
        if stats['duplicate'] > 0:
            add_log(f'检测到重复发票：{stats["duplicate"]} 张', 'warning')
        if stats['failed'] > 0:
            add_log(f'识别失败发票：{stats["failed"]} 张', 'error')
            for f in stats.get('failed_files', []):
                reason_cn = err_to_cn(f.get('reason', ''))
                f['reason_cn'] = reason_cn
                add_log(f'处理失败: {f["filename"]} — {reason_cn}', 'error')

        add_log('处理流程结束', 'info')
        with _pipeline_lock:
            _pipeline_result['stats'] = stats
            _pipeline_result['error'] = None
            _pipeline_result['running'] = False
    except Exception as e:
        cn_msg = err_to_cn(str(e))
        add_log(f'处理异常：{cn_msg}', 'error')
        with _pipeline_lock:
            _pipeline_result['error'] = cn_msg
            _pipeline_result['running'] = False


@tasks_bp.route('/api/tasks/process', methods=['POST'])
def process_invoices():
    try:
        with _pipeline_lock:
            if _pipeline_result['running']:
                return {'status': 'error', 'message': '处理任务正在执行中，请等待完成'}, 409
            _pipeline_result['running'] = True

        thread = threading.Thread(target=_run_pipeline_async, daemon=True)
        thread.start()

        return {'status': 'success', 'message': '处理任务已启动'}
    except Exception as e:
        return api_error(str(e))


@tasks_bp.route('/api/tasks/status', methods=['GET'])
def get_pipeline_status():
    try:
        with _pipeline_lock:
            running = _pipeline_result['running']
            stats = _pipeline_result['stats']
            error = _pipeline_result['error']
        return {
            'status': 'success',
            'data': {
                'running': running,
                'stats': stats,
                'error': error
            }
        }
    except Exception as e:
        return api_error(str(e))


@tasks_bp.route('/api/logs', methods=['GET'])
def get_logs():
    try:
        count = int(request.args.get('count', 50))
        logs = get_recent_logs(count)
        return {'status': 'success', 'data': logs}
    except Exception as e:
        return api_error(str(e))


@tasks_bp.route('/api/logs/clear', methods=['POST'])
def clear_process_logs():
    try:
        clear_logs()
        return {'status': 'success', 'message': '日志已清空'}
    except Exception as e:
        return api_error(str(e))


@tasks_bp.route('/api/logs/add', methods=['POST'])
def add_process_log():
    try:
        data = request.get_json()
        message = data.get('message', '')
        level = data.get('level', 'info')
        add_log(message, level)
        return {'status': 'success'}
    except Exception as e:
        return api_error(str(e))
