import logging
import time
import sqlite3
from datetime import datetime

logger = logging.getLogger(__name__)


class LocksMixin:
    def acquire_file_lock(self, file_path, lock_holder, timeout=30, retry_interval=0.5):
        start_time = time.time()
        while time.time() - start_time < timeout:
            conn = self._get_connection()
            cursor = conn.cursor()
            lock_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                cursor.execute("""
                    INSERT INTO file_locks (file_path, lock_holder, lock_time)
                    VALUES (?, ?, ?)
                """, (file_path, lock_holder, lock_time))
                conn.commit()
                conn.close()
                logger.debug(f"获取文件锁成功: {file_path}")
                return True
            except sqlite3.IntegrityError:
                cursor.execute("SELECT lock_holder, lock_time FROM file_locks WHERE file_path = ?", (file_path,))
                row = cursor.fetchone()
                conn.close()
                if row:
                    logger.debug(f"文件已被其他实例锁定: {file_path}, 持有者: {row[0]}, 锁定时间: {row[1]}")
                time.sleep(retry_interval)
            except Exception as e:
                conn.close()
                logger.error(f"获取文件锁异常: {file_path}, 错误: {e}")
                time.sleep(retry_interval)

        logger.warning(f"获取文件锁超时: {file_path}")
        return False

    def release_file_lock(self, file_path, lock_holder):
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                DELETE FROM file_locks
                WHERE file_path = ? AND lock_holder = ?
            """, (file_path, lock_holder))
            conn.commit()
            deleted = cursor.rowcount > 0
            conn.close()
            if deleted:
                logger.debug(f"释放文件锁成功: {file_path}")
            else:
                logger.warning(f"释放文件锁失败(锁不存在或不属于当前持有者): {file_path}")
            return deleted
        except Exception as e:
            conn.close()
            logger.error(f"释放文件锁异常: {file_path}, 错误: {e}")
            return False
