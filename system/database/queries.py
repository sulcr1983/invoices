import logging
from datetime import datetime

from .connection import DBManager

logger = logging.getLogger(__name__)


def query_records(self, invoice_num=None, seller=None, buyer=None,
                  date_from=None, date_to=None, invoice_type=None,
                  push_status=None, keyword=None,
                  amt_from=None, amt_to=None,
                  order_by="process_time", order_dir="DESC",
                  limit=None, offset=None):
    conn = self._get_connection()
    cursor = conn.cursor()

    conditions = []
    params = []
    if invoice_num:
        conditions.append("invoice_num LIKE ?")
        params.append(f"%{invoice_num}%")
    if seller:
        conditions.append("seller LIKE ?")
        params.append(f"%{seller}%")
    if buyer:
        conditions.append("buyer LIKE ?")
        params.append(f"%{buyer}%")
    if date_from:
        conditions.append("date >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("date <= ?")
        params.append(date_to)
    if amt_from is not None:
        conditions.append("total_amount >= ?")
        params.append(float(amt_from))
    if amt_to is not None:
        conditions.append("total_amount <= ?")
        params.append(float(amt_to))
    if invoice_type:
        conditions.append("invoice_type = ?")
        params.append(invoice_type)
    if push_status:
        conditions.append("push_status = ?")
        params.append(push_status)
    if keyword:
        conditions.append("(invoice_num LIKE ? OR seller LIKE ? OR buyer LIKE ? OR item LIKE ?)")
        kw = f"%{keyword}%"
        params.extend([kw, kw, kw, kw])

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    safe_order_cols = {"process_time", "date", "invoice_num", "seller", "buyer",
                       "total_amount", "push_status", "id"}
    if order_by not in safe_order_cols:
        order_by = "process_time"
    if order_dir.upper() not in ("ASC", "DESC"):
        order_dir = "DESC"

    sql = f"SELECT * FROM records {where_clause} ORDER BY {order_by} {order_dir}"
    if limit:
        sql += f" LIMIT {int(limit)}"
        if offset:
            sql += f" OFFSET {int(offset)}"

    cursor.execute(sql, params)
    col_names = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    cursor.execute(f"SELECT COUNT(*) FROM records {where_clause}", params)
    total = cursor.fetchone()[0]
    records = [dict(zip(col_names, row)) for row in rows]
    conn.close()
    return records, total


def get_record_by_invoice_num(self, invoice_num):
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM records WHERE invoice_num = ?", (invoice_num,))
    row = cursor.fetchone()
    result = dict(zip([desc[0] for desc in cursor.description], row)) if row else None
    conn.close()
    return result


def get_invoice_nums_ordered(self, order_by="process_time", order_dir="DESC",
                             invoice_num=None, seller=None, buyer=None,
                             date_from=None, date_to=None, invoice_type=None,
                             push_status=None, keyword=None):
    conn = self._get_connection()
    cursor = conn.cursor()
    conditions = []
    params = []
    if invoice_num:
        conditions.append("invoice_num LIKE ?")
        params.append(f"%{invoice_num}%")
    if seller:
        conditions.append("seller LIKE ?")
        params.append(f"%{seller}%")
    if buyer:
        conditions.append("buyer LIKE ?")
        params.append(f"%{buyer}%")
    if date_from:
        conditions.append("date >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("date <= ?")
        params.append(date_to)
    if invoice_type:
        conditions.append("invoice_type = ?")
        params.append(invoice_type)
    if push_status:
        conditions.append("push_status = ?")
        params.append(push_status)
    if keyword:
        conditions.append("(invoice_num LIKE ? OR seller LIKE ? OR buyer LIKE ? OR item LIKE ?)")
        kw = f"%{keyword}%"
        params.extend([kw, kw, kw, kw])
    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)
    safe_order_cols = {"process_time", "date", "invoice_num", "seller", "buyer",
                       "total_amount", "push_status", "id"}
    if order_by not in safe_order_cols:
        order_by = "process_time"
    if order_dir.upper() not in ("ASC", "DESC"):
        order_dir = "DESC"
    cursor.execute(f"SELECT invoice_num FROM records {where_clause} ORDER BY {order_by} {order_dir}", params)
    nums = [r[0] for r in cursor.fetchall()]
    conn.close()
    return nums


def record_exists(self, invoice_num):
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM records WHERE invoice_num = ?", (invoice_num,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists


def record_exists_by_md5(self, file_md5):
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM records WHERE file_md5 = ?", (file_md5,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists


def get_record_by_md5(self, file_md5):
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM records WHERE file_md5 = ?", (file_md5,))
    row = cursor.fetchone()
    conn.close()
    return row


def get_stats(self):
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM records")
    total_cnt = cursor.fetchone()[0]
    cursor.execute("SELECT COALESCE(SUM(total_amount),0) FROM records")
    total_amt = cursor.fetchone()[0]
    now = datetime.now()
    cursor.execute("SELECT COUNT(*), COALESCE(SUM(total_amount),0) FROM records WHERE strftime('%Y-%m', date) = ?",
                   (now.strftime("%Y-%m"),))
    row = cursor.fetchone()
    conn.close()
    return {"total_cnt": total_cnt, "total_amt": total_amt, "month_cnt": row[0], "month_amt": row[1]}


def get_recent_records(self, limit=10):
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT invoice_num, seller, item, total_amount, date FROM records ORDER BY process_time DESC LIMIT ?",
        (limit,))
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_distinct_values(self, column):
    safe_cols = {"seller", "buyer", "invoice_type", "invoice_num", "push_status"}
    if column not in safe_cols:
        logger.warning(f"不允许的列名: {column}")
        return []
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT DISTINCT {column} FROM records WHERE {column} IS NOT NULL AND {column} != '' ORDER BY {column}")
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]


def get_failed_count(self):
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM records WHERE push_status = 'failed'")
    count = cursor.fetchone()[0]
    conn.close()
    return count


def get_unsynced_count(self):
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM records WHERE sync_status = 0")
    count = cursor.fetchone()[0]
    conn.close()
    return count


def get_pending_count(self):
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM records WHERE push_status = 'pending'")
    count = cursor.fetchone()[0]
    conn.close()
    return count


def get_push_status(self, invoice_num):
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT push_status, retry_count FROM records WHERE invoice_num = ?", (invoice_num,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row[0], row[1]
    return None, None


def get_invoice_id_by_num(self, invoice_num):
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM records WHERE invoice_num = ?", (invoice_num,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def get_invoice_details(self, invoice_id):
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, item_name, tax_rate, amount, tax_amount
        FROM invoice_details WHERE invoice_id = ? ORDER BY id
    """, (invoice_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_unsynced_records(self):
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM records WHERE sync_status = 0")
    rows = cursor.fetchall()
    conn.close()
    return rows


RECORD_COLUMNS = ['invoice_num', 'seller', 'seller_tax_id',
                  'date', 'buyer', 'buyer_tax_id', 'item',
                  'price_without_tax', 'tax_rate', 'tax_amount', 'total_amount',
                  'invoice_code', 'check_code', 'invoice_type', 'remark',
                  'file_md5', 'sync_status', 'push_status',
                  'retry_count', 'last_error', 'process_time', 'error_type']


def get_unsynced_records_as_dicts(self):
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT {','.join(RECORD_COLUMNS)} FROM records WHERE sync_status = 0")
    rows = cursor.fetchall()
    conn.close()
    return [dict(zip(RECORD_COLUMNS, row)) for row in rows]


def get_pending_push_records(self):
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT {','.join(RECORD_COLUMNS)} FROM records WHERE push_status != 'success' AND retry_count < 3")
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_records_for_compensate(self):
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT {','.join(RECORD_COLUMNS)} FROM records WHERE push_status = 'failed' AND retry_count < 3")
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_duplicate_records(self, limit=50, offset=0):
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM duplicate_records")
    total = cursor.fetchone()[0]
    cursor.execute("""
        SELECT id, invoice_num, seller, date, total_amount, invoice_code,
               file_md5, duplicate_type, existing_invoice_num, filename,
               batch_id, detected_at
        FROM duplicate_records ORDER BY detected_at DESC LIMIT ? OFFSET ?
    """, (limit, offset))
    col_names = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    records = [dict(zip(col_names, row)) for row in rows]
    conn.close()
    return records, total


def get_duplicate_stats(self):
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM duplicate_records")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(DISTINCT invoice_num) FROM duplicate_records WHERE invoice_num IS NOT NULL AND invoice_num != ''")
    unique_invoices = cursor.fetchone()[0]
    cursor.execute("""
        SELECT duplicate_type, COUNT(*) as cnt FROM duplicate_records
        GROUP BY duplicate_type
    """)
    type_stats = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    return {'total': total, 'unique_invoices': unique_invoices, 'type_stats': type_stats}


# 注册方法到 DBManager
QUERY_METHODS = [
    query_records, get_record_by_invoice_num, get_invoice_nums_ordered,
    record_exists, record_exists_by_md5, get_record_by_md5,
    get_stats, get_recent_records, get_distinct_values,
    get_failed_count, get_unsynced_count, get_pending_count,
    get_push_status, get_invoice_id_by_num, get_invoice_details,
    get_unsynced_records, get_unsynced_records_as_dicts,
    get_pending_push_records, get_records_for_compensate,
    get_duplicate_records, get_duplicate_stats,
]
for fn in QUERY_METHODS:
    setattr(DBManager, fn.__name__, fn)
