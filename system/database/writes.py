import logging
from datetime import datetime

from .connection import DBManager
from ..config import INVOICE_FIELD_NAMES, LEDGER_PATH

logger = logging.getLogger(__name__)


def update_remark(self, invoice_num, remark):
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE records SET remark = ? WHERE invoice_num = ?", (remark, invoice_num))
    conn.commit()
    affected = cursor.rowcount > 0
    conn.close()
    if affected:
        logger.info(f"备注更新: {invoice_num}")
    return affected


def insert_record_with_transaction(self, record_dict, batch_id=None):
    with self.Transaction(self) as txn:
        cursor = txn.cursor
        process_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        record_dict['process_time'] = process_time
        record_dict['batch_id'] = batch_id
        record_dict['error_type'] = None

        try:
            cursor.execute("""
                INSERT INTO records (
                    invoice_num, seller, seller_tax_id,
                    date, buyer, buyer_tax_id, item,
                    price_without_tax, tax_rate, tax_amount, total_amount,
                    invoice_code, check_code, invoice_type, remark,
                    file_md5, sync_status, push_status,
                    retry_count, last_error, process_time, batch_id,
                    error_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record_dict.get('invoice_num', ''),
                record_dict.get('seller', ''),
                record_dict.get('seller_tax_id', ''),
                record_dict.get('date', ''),
                record_dict.get('buyer', ''),
                record_dict.get('buyer_tax_id', ''),
                record_dict.get('item', ''),
                record_dict.get('price_without_tax', 0.00),
                record_dict.get('tax_rate', ''),
                record_dict.get('tax_amount', 0.00),
                record_dict.get('total_amount', 0.00),
                record_dict.get('invoice_code', ''),
                record_dict.get('check_code', ''),
                record_dict.get('invoice_type', ''),
                record_dict.get('remark', ''),
                record_dict.get('file_md5', ''),
                record_dict.get('sync_status', 0),
                'pending', 0, '',
                process_time, batch_id, None
            ))
            logger.info(f"记录插入成功: {record_dict.get('invoice_num')}")
            return True, 'inserted', record_dict
        except Exception as e:
            err_str = str(e)
            if 'idx_records_md5' in err_str or 'file_md5' in err_str:
                logger.warning(f"文件MD5重复: {record_dict.get('file_md5')}")
                record_dict['error_type'] = 'duplicate_md5'
                return False, 'duplicate_md5', record_dict
            elif 'invoice_num' in err_str:
                logger.warning(f"发票号码重复: {record_dict.get('invoice_num')}")
                record_dict['error_type'] = 'duplicate_invoice_num'
                return False, 'duplicate_invoice_num', record_dict
            else:
                logger.error(f"数据库IntegrityError: {e}")
                record_dict['error_type'] = 'integrity_error'
                return False, 'integrity_error', record_dict


def insert_record(self, record_dict, batch_id=None):
    success, reason, _ = self.insert_record_with_transaction(record_dict, batch_id)
    return success, reason


def update_sync_status(self, invoice_num, sync_status=1):
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE records SET sync_status = ? WHERE invoice_num = ?", (sync_status, invoice_num))
    conn.commit()
    conn.close()
    logger.info(f"同步状态更新: {invoice_num} -> {sync_status}")


def update_error_type(self, invoice_num, error_type, last_error):
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE records SET error_type = ?, last_error = ?, push_status = 'failed'
        WHERE invoice_num = ?
    """, (error_type, last_error, invoice_num))
    conn.commit()
    conn.close()
    logger.error(f"记录错误类型: {invoice_num}, error_type={error_type}")


def insert_invoice_details(self, invoice_id, details):
    conn = self._get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM invoice_details WHERE invoice_id = ?", (invoice_id,))
        for detail in details:
            cursor.execute("""
                INSERT INTO invoice_details (invoice_id, item_name, tax_rate, amount, tax_amount)
                VALUES (?, ?, ?, ?, ?)
            """, (
                invoice_id,
                detail.get('item_name', ''),
                detail.get('tax_rate', ''),
                detail.get('amount', 0.0),
                detail.get('tax_amount', 0.0)
            ))
        conn.commit()
        logger.info(f"发票明细插入成功: invoice_id={invoice_id}, 明细行数={len(details)}")
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"发票明细插入失败: {e}")
        return False
    finally:
        conn.close()


def verify_invoice_math(self, invoice_id):
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0), COALESCE(SUM(tax_amount), 0)
        FROM invoice_details WHERE invoice_id = ?
    """, (invoice_id,))
    detail_row = cursor.fetchone()
    detail_total = detail_row[0] + detail_row[1]
    cursor.execute("SELECT total_amount FROM records WHERE id = ?", (invoice_id,))
    inv_row = cursor.fetchone()
    if not inv_row:
        conn.close()
        return False, "发票记录不存在"
    face_total = inv_row[0] or 0.0
    diff = round(detail_total - face_total, 2)
    cursor.execute("UPDATE records SET verify_diff = ? WHERE id = ?", (diff, invoice_id))
    conn.commit()
    conn.close()
    if diff == 0:
        logger.info(f"发票校验通过: invoice_id={invoice_id}")
        return True, "校验通过"
    else:
        logger.warning(f"发票校验差额: invoice_id={invoice_id}, 差额={diff}")
        return False, f"校验差额: {diff}"


def export_to_csv(self, ledger_path=None):
    import pandas as pd
    csv_path = ledger_path or LEDGER_PATH
    conn = self._get_connection()
    df = pd.read_sql_query("SELECT * FROM records ORDER BY process_time DESC", conn)
    conn.close()
    df.rename(columns=INVOICE_FIELD_NAMES, inplace=True)
    available_cols = [col for col in df.columns if col in INVOICE_FIELD_NAMES.values()]
    df = df[[col for col in INVOICE_FIELD_NAMES.values() if col in available_cols]]
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    logger.info(f"账本导出成功: {csv_path}")
    return csv_path


def log_duplicate_record(self, invoice_num='', seller='', date='', total_amount=0,
                         invoice_code='', file_md5='', duplicate_type='',
                         existing_invoice_num='', filename='', batch_id=''):
    conn = self._get_connection()
    cursor = conn.cursor()
    detected_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        cursor.execute("""
            INSERT INTO duplicate_records (
                invoice_num, seller, date, total_amount, invoice_code,
                file_md5, duplicate_type, existing_invoice_num, filename,
                batch_id, detected_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            invoice_num, seller, date, total_amount, invoice_code,
            file_md5, duplicate_type, existing_invoice_num, filename,
            batch_id, detected_at
        ))
        conn.commit()
        logger.info(f"重复发票记录已保存: {invoice_num}, 类型={duplicate_type}")
    except Exception as e:
        logger.error(f"保存重复发票记录失败: {e}")
    finally:
        conn.close()


# 注册方法到 DBManager
WRITE_METHODS = [
    update_remark, insert_record_with_transaction, insert_record,
    update_sync_status, update_error_type, insert_invoice_details,
    verify_invoice_math, export_to_csv, log_duplicate_record,
]
for fn in WRITE_METHODS:
    setattr(DBManager, fn.__name__, fn)
