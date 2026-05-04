import sys
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

_THIS_DIR = str(Path(__file__).resolve().parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)
_PARENT_DIR = str(Path(__file__).resolve().parent.parent)
if _PARENT_DIR not in sys.path:
    sys.path.insert(0, _PARENT_DIR)

try:
    from .db_manager import DBManager
    from .config import DB_PATH, LOG_PATH, ARCHIVE_DIR, PROJECT_ROOT, err_to_cn
except ImportError:
    from db_manager import DBManager
    from config import DB_PATH, LOG_PATH, ARCHIVE_DIR, PROJECT_ROOT, err_to_cn

db_manager = DBManager(DB_PATH)
process_logs = []


def add_log(message, level='info'):
    timestamp = datetime.now().strftime('%H:%M:%S')
    log_entry = {'timestamp': timestamp, 'message': message, 'level': level}
    process_logs.append(log_entry)
    if len(process_logs) > 100:
        process_logs.pop(0)
    return log_entry


def get_recent_logs(count=50):
    return process_logs[-count:] if len(process_logs) >= count else process_logs


def clear_logs():
    process_logs.clear()
    add_log('日志已清空', 'info')
    return True


def api_error(message, status_code=500):
    cn_msg = err_to_cn(message)
    logger.exception(f"API错误: {cn_msg}")
    return {'status': 'error', 'message': cn_msg}, status_code
