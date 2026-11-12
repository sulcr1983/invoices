import logging
import threading
from collections import deque
from datetime import datetime

from ..db_manager import DBManager
from ..config import DB_PATH, LOG_PATH, ARCHIVE_DIR, PROJECT_ROOT, err_to_cn

logger = logging.getLogger(__name__)

db_manager = DBManager(DB_PATH)
_logs_lock = threading.Lock()
process_logs = deque(maxlen=100)
_log_seq = 0


def add_log(message, level='info'):
    """追加一条内存日志，带单调递增 seq，便于前端做增量拉取。"""
    global _log_seq
    _log_seq += 1
    timestamp = datetime.now().strftime('%H:%M:%S')
    log_entry = {'seq': _log_seq, 'timestamp': timestamp, 'message': message, 'level': level}
    with _logs_lock:
        process_logs.append(log_entry)
    return log_entry


def get_recent_logs(count=50):
    with _logs_lock:
        snapshot = list(process_logs)
    return snapshot[-count:] if len(snapshot) >= count else snapshot


def get_logs_since(since_seq=0):
    """返回 seq 大于 since_seq 的日志（增量）。"""
    with _logs_lock:
        snapshot = list(process_logs)
    return [entry for entry in snapshot if entry.get('seq', 0) > since_seq]


def get_latest_seq():
    return _log_seq


def clear_logs():
    with _logs_lock:
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
