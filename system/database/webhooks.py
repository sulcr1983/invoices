import logging
from datetime import datetime

from .columns import RECORD_COLUMNS

logger = logging.getLogger(__name__)

WEBHOOK_COLUMNS = ['id', 'name', 'platform', 'url', 'schema_json', 'enabled',
                   'retry_count', 'max_retries', 'last_push', 'last_status',
                   'last_error', 'created_at']


class WebhooksMixin:
    def get_all_webhooks(self, only_enabled=False):
        with self.connection() as conn:
            cursor = conn.cursor()
            if only_enabled:
                cursor.execute("SELECT * FROM webhooks WHERE enabled=1 ORDER BY id")
            else:
                cursor.execute("SELECT * FROM webhooks ORDER BY id")
            rows = cursor.fetchall()
            return [dict(zip(WEBHOOK_COLUMNS, row)) for row in rows]

    def add_webhook(self, name, platform, url, schema_json=None):
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO webhooks (name, platform, url, schema_json, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (name, platform, url, schema_json, created_at))
            conn.commit()
            hook_id = cursor.lastrowid
            logger.info(f"新增推送目标: {name} ({platform}) id={hook_id}")
            return hook_id

    def update_webhook(self, hook_id, name=None, platform=None, url=None,
                       schema_json=None, enabled=None, max_retries=None):
        with self.connection() as conn:
            cursor = conn.cursor()
            fields = []
            vals = []
            if name is not None:
                fields.append("name=?")
                vals.append(name)
            if platform is not None:
                fields.append("platform=?")
                vals.append(platform)
            if url is not None:
                fields.append("url=?")
                vals.append(url)
            if schema_json is not None:
                fields.append("schema_json=?")
                vals.append(schema_json)
            if enabled is not None:
                fields.append("enabled=?")
                vals.append(int(enabled))
            if max_retries is not None:
                fields.append("max_retries=?")
                vals.append(max_retries)
            if not fields:
                return False
            vals.append(hook_id)
            cursor.execute(f"UPDATE webhooks SET {', '.join(fields)} WHERE id=?", vals)
            conn.commit()
            affected = cursor.rowcount > 0
            if affected:
                logger.info(f"更新推送目标 id={hook_id}")
            return affected

    def delete_webhook(self, hook_id):
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM webhooks WHERE id=?", (hook_id,))
            conn.commit()
            affected = cursor.rowcount > 0
            if affected:
                logger.info(f"删除推送目标 id={hook_id}")
            return affected

    def update_webhook_push_result(self, hook_id, status, error_msg=None):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE webhooks SET last_push=?, last_status=?, last_error=?
                WHERE id=?
            """, (now, status, error_msg or '', hook_id))
            conn.commit()

    def add_push_history(self, invoice_num, webhook_id, platform, status,
                         error_msg=None, retry_num=0):
        push_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO push_history (invoice_num, webhook_id, platform, status, error_msg, push_time, retry_num)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (invoice_num, webhook_id, platform, status, error_msg or '', push_time, retry_num))
            conn.commit()

    def update_push_success(self, invoice_num):
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE records
                SET push_status = 'success', sync_status = 1, last_error = ''
                WHERE invoice_num = ?
            """, (invoice_num,))
            conn.commit()
            logger.info(f"推送成功更新: {invoice_num}")

    def update_push_failed(self, invoice_num, retry_count, last_error, error_type='api_error'):
        with self.connection() as conn:
            cursor = conn.cursor()
            new_status = 'failed' if retry_count >= 3 else 'pending'
            cursor.execute("""
                UPDATE records
                SET push_status = ?, retry_count = ?, last_error = ?, error_type = ?
                WHERE invoice_num = ?
            """, (new_status, retry_count, last_error, error_type, invoice_num))
            conn.commit()
            if new_status == 'failed':
                logger.warning(f"推送失败(已达最大重试): {invoice_num}, 错误: {last_error}")
            else:
                logger.warning(f"推送失败(将重试): {invoice_num}, 错误: {last_error}")
