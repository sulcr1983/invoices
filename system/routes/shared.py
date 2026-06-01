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


def add_log(message, level='info'):
    timestamp = datetime.now().strftime('%H:%M:%S')
    log_entry = {'timestamp': timestamp, 'message': message, 'level': level}
    with _logs_lock:
        process_logs.append(log_entry)
    return log_entry


def get_recent_logs(count=50):
    with _logs_lock:
        logs = list(process_logs)
    return logs[-count:] if len(logs) >= count else logs


def clear_logs():
    with _logs_lock:
        process_logs.clear()
    add_log('日志已清空', 'info')
    return True


def api_error(message, status_code=500):
    cn_msg = err_to_cn(message)
    logger.exception(f"API错误: {cn_msg}")
    return {'status': 'error', 'message': cn_msg}, status_code
