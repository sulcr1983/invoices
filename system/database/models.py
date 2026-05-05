import logging

logger = logging.getLogger(__name__)


class ModelsMixin:
    def _init_records_table(self):
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='records'")
        table_exists = cursor.fetchone() is not None

        if not table_exists:
            cursor.execute("""
                CREATE TABLE records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    invoice_num TEXT,
                    seller TEXT,
                    seller_tax_id TEXT,
                    date TEXT,
                    buyer TEXT,
                    buyer_tax_id TEXT,
                    item TEXT,
                    price_without_tax REAL,
                    tax_rate TEXT,
                    tax_amount REAL,
                    total_amount REAL,
                    invoice_code TEXT,
                    check_code TEXT,
                    invoice_type TEXT,
                    remark TEXT,
                    file_md5 TEXT,
                    sync_status INTEGER DEFAULT 0,
                    push_status TEXT DEFAULT 'pending',
                    retry_count INTEGER DEFAULT 0,
                    last_error TEXT,
                    process_time TEXT,
                    batch_id TEXT,
                    error_type TEXT,
                    verify_diff REAL DEFAULT 0,
                    verify_status TEXT DEFAULT 'unverified',
                    verify_time TEXT,
                    verify_result TEXT,
                    deduction_status TEXT DEFAULT 'unverified',
                    certification_date TEXT,
                    department TEXT,
                    project TEXT,
                    expense_type TEXT,
                    risk_flags TEXT
                )
            """)
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_records_md5 ON records(file_md5)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_records_date ON records(date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_records_seller ON records(seller)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_records_buyer ON records(buyer)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_records_total_amount ON records(total_amount)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_records_process_time ON records(process_time)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_records_invoice_type ON records(invoice_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_records_invoice_num ON records(invoice_num)")
            conn.commit()
            conn.close()
            logger.info("数据库初始化完成（新表结构）")
            return

        cursor.execute("PRAGMA table_info(records)")
        existing_cols = {row[1] for row in cursor.fetchall()}

        if 'id' not in existing_cols:
            self._migrate_old_schema(cursor, existing_cols)
            cursor.execute("PRAGMA table_info(records)")
            existing_cols = {row[1] for row in cursor.fetchall()}

        migrations = [
            ("push_status", "TEXT DEFAULT 'pending'"),
            ("retry_count", "INTEGER DEFAULT 0"),
            ("last_error", "TEXT"),
            ("batch_id", "TEXT"),
            ("error_type", "TEXT"),
            ("remark", "TEXT"),
            ("verify_diff", "REAL DEFAULT 0"),
            ("verify_status", "TEXT DEFAULT 'unverified'"),
            ("verify_time", "TEXT"),
            ("verify_result", "TEXT"),
            ("deduction_status", "TEXT DEFAULT 'unverified'"),
            ("certification_date", "TEXT"),
            ("department", "TEXT"),
            ("project", "TEXT"),
            ("expense_type", "TEXT"),
            ("risk_flags", "TEXT"),
        ]
        for col_name, col_type in migrations:
            if col_name not in existing_cols:
                try:
                    cursor.execute(f"ALTER TABLE records ADD COLUMN {col_name} {col_type}")
                except Exception:
                    pass

        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_records_invoice_num ON records(invoice_num)")
        except Exception:
            pass

        conn.commit()
        conn.close()
        logger.info("数据库初始化完成")

    @staticmethod
    def _migrate_old_schema(cursor, existing_cols):
        logger.info("检测到旧表结构，开始迁移：添加 id 主键...")
        try:
            cursor.execute("ALTER TABLE records ADD COLUMN id INTEGER")
        except Exception:
            pass

        cursor.execute("SELECT rowid FROM records ORDER BY rowid")
        rows = cursor.fetchall()
        for i, (rowid,) in enumerate(rows, 1):
            cursor.execute("UPDATE records SET id = ? WHERE rowid = ?", (i, rowid))

        cursor.execute("CREATE TABLE records_new (id INTEGER PRIMARY KEY AUTOINCREMENT)")
        cursor.execute("SELECT name FROM pragma_table_info('records') WHERE name != 'id'")
        old_col_names = [r[0] for r in cursor.fetchall()]
        for name in old_col_names:
            cursor.execute(f"SELECT type FROM pragma_table_info('records') WHERE name='{name}'")
            row = cursor.fetchone()
            col_type = row[0] if row and row[0] else "TEXT"
            cursor.execute(f"ALTER TABLE records_new ADD COLUMN {name} {col_type}")

        col_list_new = ", ".join(old_col_names)
        cursor.execute(f"INSERT INTO records_new ({col_list_new}) SELECT {col_list_new} FROM records")
        cursor.execute("DROP TABLE records")
        cursor.execute("ALTER TABLE records_new RENAME TO records")

        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_records_md5 ON records(file_md5)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_records_date ON records(date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_records_seller ON records(seller)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_records_buyer ON records(buyer)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_records_total_amount ON records(total_amount)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_records_process_time ON records(process_time)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_records_invoice_type ON records(invoice_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_records_invoice_num ON records(invoice_num)")
        logger.info("数据库迁移完成：id 主键已添加")

    def _init_webhooks_table(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS webhooks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                platform TEXT NOT NULL,
                url TEXT NOT NULL,
                schema_json TEXT,
                enabled INTEGER DEFAULT 1,
                retry_count INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,
                last_push TEXT,
                last_status TEXT,
                last_error TEXT,
                created_at TEXT
            )
        """)
        conn.commit()
        conn.close()

    def _init_push_history_table(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS push_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_num TEXT NOT NULL,
                webhook_id INTEGER,
                platform TEXT NOT NULL,
                status TEXT,
                error_msg TEXT,
                push_time TEXT,
                retry_num INTEGER DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()

    def _init_lock_table(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_locks (
                file_path TEXT PRIMARY KEY,
                lock_holder TEXT,
                lock_time TEXT,
                UNIQUE(file_path)
            )
        """)
        conn.commit()
        conn.close()

    def _init_invoice_details_table(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS invoice_details (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL,
                item_name TEXT,
                tax_rate TEXT,
                amount REAL,
                tax_amount REAL,
                FOREIGN KEY (invoice_id) REFERENCES records(id)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_details_invoice_id ON invoice_details(invoice_id)")
        conn.commit()
        conn.close()
        logger.info("发票明细表初始化完成")

    def _init_duplicate_records_table(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS duplicate_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_num TEXT,
                seller TEXT,
                date TEXT,
                total_amount REAL,
                invoice_code TEXT,
                file_md5 TEXT,
                duplicate_type TEXT,
                existing_invoice_num TEXT,
                filename TEXT,
                batch_id TEXT,
                detected_at TEXT
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dup_records_invoice_num ON duplicate_records(invoice_num)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dup_records_detected_at ON duplicate_records(detected_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dup_records_duplicate_type ON duplicate_records(duplicate_type)")
        conn.commit()
        conn.close()
        logger.info("重复发票记录表初始化完成")
