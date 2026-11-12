import logging
import time
import sqlite3
from datetime import datetime

logger = logging.getLogger(__name__)


class LocksMixin:
    LOCK_TTL_SECONDS = 1800  # 锁超过 30 分钟视为进程崩溃残留

    def _clear_stale_locks(self):
        """清理崩溃进程遗留的过期锁，避免文件被永久锁死。"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT file_path, lock_time FROM file_locks")
            stale = []
            now = datetime.now()
            for file_path, lock_time in cursor.fetchall():
                try:
                    locked_at = datetime.strptime(lock_time, "%Y-%m-%d %H:%M:%S")
                except (TypeError, ValueError):
                    stale.append(file_path)
                    continue
                if (now - locked_at).total_seconds() > self.LOCK_TTL_SECONDS:
                    stale.append(file_path)
            for file_path in stale:
                cursor.execute("DELETE FROM file_locks WHERE file_path = ?", (file_path,))
            if stale:
                conn.commit()
                logger.warning(f"清理过期文件锁 {len(stale)} 个")
        except Exception as e:
            logger.error(f"清理过期锁失败: {e}")
        finally:
            conn.close()

    def acquire_file_lock(self, file_path, lock_holder, timeout=30, retry_interval=0.5):
        self._clear_stale_locks()
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
