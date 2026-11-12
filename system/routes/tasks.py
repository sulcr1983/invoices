import logging
import re
import threading
from pathlib import Path
from flask import Blueprint, request

from .shared import db_manager, api_error, add_log, get_recent_logs, clear_logs, err_to_cn

tasks_bp = Blueprint('tasks', __name__)

_ALLOWED_UPLOAD_EXTS = {'.pdf', '.ofd', '.jpg', '.jpeg', '.png'}


def _safe_upload_name(raw_name):
    """清洗上传文件名：剥离路径分隔符与危险字符，保留中文与扩展名。

    防目录穿越：只保留 basename，去掉 \\ / 空字节及控制字符。
    若清洗后为空或后缀不在白名单，返回 None 表示拒绝。
    """
    if not raw_name:
        return None
    name = raw_name.replace('\\', '/').split('/')[-1]
    name = ''.join(ch for ch in name if ch >= ' ' and ch != '\x7f')
    name = re.sub(r'[<>:"|?*]', '', name)
    name = name.strip().strip('.')
    if not name:
        return None
    if Path(name).suffix.lower() not in _ALLOWED_UPLOAD_EXTS:
        return None
    return name


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
    """接收前端上传的发票文件，并保存到待识别目录。

    安全要点：
    - 文件名经 _safe_upload_name 清洗，剥离路径分隔符，防目录穿越；
    - 后缀白名单校验，非发票格式拒绝，避免任意文件进入处理流水线。
    """
    try:
        from ..config import INPUT_DIR
        from ..services import ensure_directories
        ensure_directories()
        files = request.files.getlist('files')
        if not files:
            return {'status': 'error', 'message': '没有选择文件'}, 400

        uploaded = []
        skipped = []
        rejected = []
        input_dir = Path(str(INPUT_DIR))
        for f in files:
            if f.filename == '':
                continue
            safe_name = _safe_upload_name(f.filename)
            if safe_name is None:
                rejected.append(f.filename)
                continue
            dest = input_dir / safe_name
            if dest.exists():
                skipped.append(safe_name)
                continue
            f.save(str(dest))
            uploaded.append(safe_name)

        return {
            'status': 'success',
            'data': {
                'uploaded': uploaded,
                'skipped': skipped,
                'rejected': rejected,
                'total': len(uploaded)
            }
        }
    except Exception as e:
        return api_error(str(e))


_pipeline_result = {'running': False, 'stats': None, 'error': None}
_pipeline_lock = threading.Lock()


def _run_pipeline_async():
    """在后台线程运行发票处理流程，并把进度写入前端日志。"""
    try:
        from ..core.pipeline import run_pipeline
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
        # 挂到 'system' 父级 logger，OCR/DB/服务层的日志才能一起进 UI
        root_system_logger = logging.getLogger('system')
        root_system_logger.addHandler(handler)

        add_log('系统就绪，等待开始处理发票...', 'info')
        add_log('开始处理发票...', 'info')

        try:
            stats, batch_id = run_pipeline()
        finally:
            root_system_logger.removeHandler(handler)

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
        _pipeline_result['stats'] = stats
        _pipeline_result['error'] = None
    except Exception as e:
        cn_msg = err_to_cn(str(e))
        add_log(f'处理异常：{cn_msg}', 'error')
        _pipeline_result['error'] = cn_msg
    finally:
        _pipeline_result['running'] = False


@tasks_bp.route('/api/tasks/process', methods=['POST'])
def process_invoices():
    """启动一次后台发票处理任务，避免重复启动并立即返回状态。"""
    try:
        # 在锁内完成「检查并占位」，消除并发双击导致启动两条流水线的竞态
        with _pipeline_lock:
            if _pipeline_result['running']:
                return {'status': 'error', 'message': '处理任务正在执行中，请等待完成'}, 409
            _pipeline_result['running'] = True

        thread = threading.Thread(target=_run_pipeline_async, daemon=True)
        thread.start()

        return {'status': 'success', 'message': '处理任务已启动'}
    except Exception as e:
        _pipeline_result['running'] = False
        return api_error(str(e))


@tasks_bp.route('/api/tasks/status', methods=['GET'])
def get_pipeline_status():
    try:
        return {
            'status': 'success',
            'data': {
                'running': _pipeline_result['running'],
                'stats': _pipeline_result['stats'],
                'error': _pipeline_result['error']
            }
        }
    except Exception as e:
        return api_error(str(e))


@tasks_bp.route('/api/logs', methods=['GET'])
def get_logs():
    """返回日志。带 since 参数时只返回新增部分（增量），避免前端重复渲染。"""
    try:
        since = request.args.get('since')
        if since is not None:
            try:
                since_seq = int(since)
            except (TypeError, ValueError):
                return {'status': 'error', 'message': 'since 参数必须为整数'}, 400
            from .shared import get_logs_since, get_latest_seq
            return {
                'status': 'success',
                'data': get_logs_since(since_seq),
                'latest_seq': get_latest_seq()
            }
        count = int(request.args.get('count', 50))
        if count < 1:
            return {'status': 'error', 'message': 'count 必须大于 0'}, 400
        logs = get_recent_logs(count)
        from .shared import get_latest_seq
        return {'status': 'success', 'data': logs, 'latest_seq': get_latest_seq()}
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
        data = request.get_json(silent=True) or {}
        message = data.get('message', '')
        level = data.get('level', 'info')
        add_log(message, level)
        return {'status': 'success'}
    except Exception as e:
        return api_error(str(e))
