import logging
import time
import sqlite3
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class LocksMixin:
    def acquire_file_lock(self, file_path, lock_holder, timeout=30, retry_interval=0.5):
        # 先清理该文件的过期锁（超过30分钟的锁视为崩溃残留）
        self._cleanup_stale_lock(file_path)

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

    def cleanup_all_stale_locks(self, max_age_minutes=30):
        """清理所有超过指定时间的过期锁，应在流水线启动时调用"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cutoff = (datetime.now() - timedelta(minutes=max_age_minutes)).strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("SELECT file_path, lock_holder FROM file_locks WHERE lock_time < ?", (cutoff,))
            stale_locks = cursor.fetchall()
            if stale_locks:
                cursor.execute("DELETE FROM file_locks WHERE lock_time < ?", (cutoff,))
                conn.commit()
                logger.info(f"已清理 {len(stale_locks)} 个过期文件锁（超过 {max_age_minutes} 分钟）")
            conn.close()
            return len(stale_locks)
        except Exception as e:
            logger.error(f"清理过期锁异常: {e}")
            return 0

    def _cleanup_stale_lock(self, file_path, max_age_minutes=30):
        """清理指定文件的过期锁"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cutoff = (datetime.now() - timedelta(minutes=max_age_minutes)).strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("DELETE FROM file_locks WHERE file_path = ? AND lock_time < ?", (file_path, cutoff))
            deleted = cursor.rowcount
            if deleted:
                conn.commit()
                logger.info(f"已清理过期锁: {file_path}")
            conn.close()
        except Exception:
            pass
