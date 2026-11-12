import sqlite3
import logging

from ..config import DB_PATH, SQLITE_TIMEOUT
from .columns import RECORD_COLUMNS
from .models import ModelsMixin
from .queries import QueriesMixin
from .writes import WritesMixin
from .webhooks import WebhooksMixin
from .locks import LocksMixin

logger = logging.getLogger(__name__)


class DBManager(ModelsMixin, QueriesMixin, WritesMixin, WebhooksMixin, LocksMixin):
    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH
        self._init_all_tables()

    def _get_connection(self):
        conn = sqlite3.connect(str(self.db_path), timeout=SQLITE_TIMEOUT)
        try:
            # WAL 提升并发读写表现；foreign_keys 让外键真正生效
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
        except sqlite3.Error as e:
            logger.warning(f"设置 SQLite PRAGMA 失败: {e}")
        return conn

    def connection(self):
        return _ConnectionContext(self)

    def backup_database(self, keep=3):
        """把当前库备份到 <db>.backup，并保留最近 keep 份。

        使用 sqlite3 的 backup API（而非直接复制文件），保证热备份一致性。
        """
        import os
        import sqlite3 as _sqlite3

        src_path = str(self.db_path)
        if not os.path.exists(src_path):
            return None
        backup_path = src_path + '.backup'
        try:
            src = _sqlite3.connect(src_path)
            dst = _sqlite3.connect(backup_path)
            with dst:
                src.backup(dst)
            src.close()
            dst.close()
            logger.info(f"数据库已备份: {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"数据库备份失败: {e}")
            return None

    def _init_all_tables(self):
        self._init_records_table()
        self._init_webhooks_table()
        self._init_push_history_table()
        self._init_invoice_details_table()
        self._init_lock_table()
        self._init_duplicate_records_table()

    class Transaction:
        def __init__(self, db_manager):
            self.db_manager = db_manager
            self.conn = None
            self.cursor = None

        def __enter__(self):
            self.conn = self.db_manager._get_connection()
            self.cursor = self.conn.cursor()
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type is not None:
                if self.conn:
                    self.conn.rollback()
                    logger.error(f"事务回滚: {exc_val}")
                if self.conn:
                    self.conn.close()
                return False
            if self.conn:
                self.conn.commit()
                self.conn.close()
            return True


class _ConnectionContext:
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.conn = None

    def __enter__(self):
        self.conn = self.db_manager._get_connection()
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()
        return False
