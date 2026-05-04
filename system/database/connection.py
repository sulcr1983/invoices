import sqlite3
import logging
from datetime import datetime

from ..config import DB_PATH, SQLITE_TIMEOUT

logger = logging.getLogger(__name__)


class DBManager:
    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH
        self._init_all_tables()

    def _get_connection(self):
        return sqlite3.connect(str(self.db_path), timeout=SQLITE_TIMEOUT)

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
