import logging
from datetime import datetime

from ..db_manager import DBManager
from ..config import DB_PATH, LOG_PATH, ARCHIVE_DIR, PROJECT_ROOT, err_to_cn

logger = logging.getLogger(__name__)

db_manager = DBManager(DB_PATH)
process_logs = []
_log_seq = 0


def add_log(message, level='info'):
    """追加一条内存日志，带单调递增 seq，便于前端做增量拉取。"""
    global _log_seq
    _log_seq += 1
    timestamp = datetime.now().strftime('%H:%M:%S')
    log_entry = {'seq': _log_seq, 'timestamp': timestamp, 'message': message, 'level': level}
    process_logs.append(log_entry)
    if len(process_logs) > 100:
        process_logs.pop(0)
    return log_entry


def get_recent_logs(count=50):
    return process_logs[-count:] if len(process_logs) >= count else process_logs


def get_logs_since(since_seq=0):
    """返回 seq 大于 since_seq 的日志（增量）。"""
    return [entry for entry in process_logs if entry.get('seq', 0) > since_seq]


def get_latest_seq():
    return _log_seq


def clear_logs():
    process_logs.clear()
    add_log('日志已清空', 'info')
    return True


def api_error(message, status_code=500):
    """记录错误并返回统一错误结构。

    只有确实处于异常上下文时才附带堆栈，避免打出 "NoneType: None" 噪声。
    """
    import sys as _sys
    cn_msg = err_to_cn(message)
    logger.error("API错误: %s", cn_msg, exc_info=_sys.exc_info()[0] is not None)
    return {'status': 'error', 'message': cn_msg}, status_code
