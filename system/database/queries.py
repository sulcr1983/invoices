import logging
from datetime import datetime

from .columns import RECORD_COLUMNS

logger = logging.getLogger(__name__)


class QueriesMixin:
    def query_records(self, invoice_num=None, seller=None, buyer=None,
                      date_from=None, date_to=None, invoice_type=None,
                      push_status=None, keyword=None, tax_rate=None,
                      amt_from=None, amt_to=None, verify_status=None, risk_flags=None,
                      order_by="process_time", order_dir="DESC",
                      limit=None, offset=None):
        with self.connection() as conn:
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
                conditions.append("invoice_type LIKE ?")
                params.append(f"%{invoice_type}%")
            if push_status:
                conditions.append("push_status = ?")
                params.append(push_status)
            if tax_rate:
                conditions.append("tax_rate LIKE ?")
                params.append(f"%{tax_rate}%")
            if verify_status:
                conditions.append("verify_status = ?")
                params.append(verify_status)
            if risk_flags:
                conditions.append("risk_flags IS NOT NULL AND risk_flags != ''")
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
            return records, total

    def get_record_by_invoice_num(self, invoice_num):
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM records WHERE invoice_num = ?", (invoice_num,))
            row = cursor.fetchone()
            result = dict(zip([desc[0] for desc in cursor.description], row)) if row else None
            return result

    def get_record_by_md5(self, file_md5):
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM records WHERE file_md5 = ?", (file_md5,))
            row = cursor.fetchone()
            if not row:
                return None
            # 统一返回 dict，避免调用方靠魔法下标取列（列顺序一变就静默取错）
            return dict(zip([d[0] for d in cursor.description], row))

    def get_status_counts(self):
        """一次查询拿到待验真 / 待认证专票 / 异常发票数量。

        前端原先拉 limit=1000 的列表在浏览器里自己数，超过 1000 条就会静默少算。
        """
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                  SUM(CASE WHEN verify_status IS NULL OR verify_status IN ('unverified','') THEN 1 ELSE 0 END),
                  SUM(CASE WHEN deduction_status = 'unverified' AND invoice_type LIKE '%专%' THEN 1 ELSE 0 END),
                  SUM(CASE WHEN risk_flags IS NOT NULL AND risk_flags != '' THEN 1 ELSE 0 END)
                FROM records
            """)
            row = cursor.fetchone() or (0, 0, 0)
            return {
                'verify_pending': int(row[0] or 0),
                'certify_pending': int(row[1] or 0),
                'risk': int(row[2] or 0),
            }

    def get_monthly_trend(self, months=6):
        """按月聚合最近 N 个月（一次查询，避免每月建一次连接）。"""
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT strftime('%Y-%m', process_time) AS m,
                       COUNT(*),
                       COALESCE(SUM(total_amount), 0),
                       COALESCE(SUM(price_without_tax), 0),
                       COALESCE(SUM(tax_amount), 0)
                FROM records
                WHERE process_time IS NOT NULL AND process_time != ''
                GROUP BY m ORDER BY m DESC LIMIT ?
            """, (months,))
            rows = cursor.fetchall()

        result = []
        now = datetime.now()
        by_month = {r[0]: r for r in rows}
        for i in range(months - 1, -1, -1):
            m = now.month - i
            y = now.year
            while m <= 0:
                m += 12
                y -= 1
            key = f"{y:04d}-{m:02d}"
            r = by_month.get(key)
            result.append({
                'month': key,
                'count': r[1] if r else 0,
                'amount': round(r[2], 2) if r else 0,
                'price': round(r[3], 2) if r else 0,
                'tax': round(r[4], 2) if r else 0,
            })
        return result

    def get_stats(self):
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM records")
            total_cnt = cursor.fetchone()[0]
            cursor.execute("SELECT COALESCE(SUM(total_amount),0) FROM records")
            total_amt = cursor.fetchone()[0]
            now = datetime.now()
            cursor.execute("SELECT COUNT(*), COALESCE(SUM(total_amount),0) FROM records WHERE strftime('%Y-%m', process_time) = ?",
                           (now.strftime("%Y-%m"),))
            row = cursor.fetchone()
            return {"total_cnt": total_cnt, "total_amt": total_amt, "month_cnt": row[0], "month_amt": row[1]}

    def get_recent_records(self, limit=10):
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT invoice_num, seller, item, total_amount, date FROM records ORDER BY process_time DESC LIMIT ?",
                (limit,))
            rows = cursor.fetchall()
            return rows

    def get_distinct_values(self, column):
        safe_cols = {"seller", "buyer", "invoice_type", "invoice_num", "push_status",
                     "department", "project", "expense_type"}
        if column not in safe_cols:
            logger.warning(f"不允许的列名: {column}")
            return []
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT DISTINCT {column} FROM records WHERE {column} IS NOT NULL AND {column} != '' ORDER BY {column}")
            rows = cursor.fetchall()
            return [r[0] for r in rows]

    def get_failed_count(self):
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM records WHERE push_status = 'failed'")
            count = cursor.fetchone()[0]
            return count

    def get_unsynced_count(self):
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM records WHERE sync_status = 0")
            count = cursor.fetchone()[0]
            return count

    def get_push_status(self, invoice_num):
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT push_status, retry_count FROM records WHERE invoice_num = ?", (invoice_num,))
            row = cursor.fetchone()
            if row:
                return row[0], row[1]
            return None, None

    def get_invoice_id_by_num(self, invoice_num):
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM records WHERE invoice_num = ?", (invoice_num,))
            row = cursor.fetchone()
            return row[0] if row else None

    def get_invoice_details(self, invoice_id):
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, item_name, tax_rate, amount, tax_amount
                FROM invoice_details WHERE invoice_id = ? ORDER BY id
            """, (invoice_id,))
            rows = cursor.fetchall()
            return rows

    def get_records_for_compensate(self):
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT {','.join(RECORD_COLUMNS)} FROM records WHERE push_status = 'failed' AND retry_count < 3")
            rows = cursor.fetchall()
            return rows

    def get_duplicate_records(self, limit=50, offset=0):
        with self.connection() as conn:
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
            return records, total

    def get_duplicate_stats(self):
        with self.connection() as conn:
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
            return {'total': total, 'unique_invoices': unique_invoices, 'type_stats': type_stats}

    def get_input_tax_summary(self, period=None, date_from=None, date_to=None):
        with self.connection() as conn:
            cursor = conn.cursor()
            today = datetime.now()
            if date_from or date_to:
                where = "WHERE invoice_type LIKE '%专%'"
                params_c = []
                params_u = []
                if date_from:
                    where += " AND date >= ?"
                    params_c.append(date_from)
                    params_u.append(date_from)
                if date_to:
                    where += " AND date <= ?"
                    params_c.append(date_to)
                    params_u.append(date_to)
                period_label = (date_from or '开始') + ' ~ ' + (date_to or '今天')
            else:
                if not period:
                    period = 'all'
                if period == 'month':
                    where = "WHERE invoice_type LIKE '%专%' AND substr(date, 1, 7) = ?"
                    period_value = today.strftime("%Y-%m")
                    period_label = today.strftime("%Y年%m月")
                elif period == 'quarter':
                    quarter_start_month = ((today.month - 1) // 3) * 3 + 1
                    quarter_end_month = quarter_start_month + 3
                    q_start = f"{today.year:04d}-{quarter_start_month:02d}-01"
                    if quarter_end_month > 12:
                        q_end = f"{today.year + 1:04d}-{quarter_end_month - 12:02d}-01"
                    else:
                        q_end = f"{today.year:04d}-{quarter_end_month:02d}-01"
                    # 季度必须有上界，否则会把未来季度的数据也算进来
                    where = "WHERE invoice_type LIKE '%专%' AND date >= ? AND date < ?"
                    params_c = [q_start, q_end]
                    params_u = [q_start, q_end]
                    period_label = f"{today.year}年第{((today.month - 1) // 3) + 1}季度"
                    period_value = None
                elif period == 'all':
                    where = "WHERE invoice_type LIKE '%专%'"
                    params_c = []
                    params_u = []
                    period_label = "全部数据"
                    period_value = None
                else:
                    where = "WHERE invoice_type LIKE '%专%' AND substr(date, 1, 4) = ?"
                    period_value = today.strftime("%Y")
                    period_label = today.strftime("%Y年")

                if period != 'all' and period != 'quarter':
                    params_c = [period_value]
                    params_u = [period_value]

            cursor.execute("""
                SELECT tax_rate,
                       COUNT(*) as cnt,
                       COALESCE(SUM(price_without_tax), 0) as total_price,
                       COALESCE(SUM(tax_amount), 0) as total_tax,
                       COALESCE(SUM(total_amount), 0) as total_amount
                FROM records
                {where} AND deduction_status = 'certified'
                GROUP BY tax_rate
                ORDER BY tax_rate
            """.format(where=where), params_c)
            certified_rows = cursor.fetchall()
            certified = []
            for row in certified_rows:
                certified.append({
                    'tax_rate': row[0],
                    'cnt': row[1],
                    'total_price': round(row[2], 2),
                    'total_tax': round(row[3], 2),
                    'total_amount': round(row[4], 2)
                })

            cursor.execute("""
                SELECT tax_rate,
                       COUNT(*) as cnt,
                       COALESCE(SUM(price_without_tax), 0) as total_price,
                       COALESCE(SUM(tax_amount), 0) as total_tax,
                       COALESCE(SUM(total_amount), 0) as total_amount
                FROM records
                {where} AND deduction_status = 'unverified'
                GROUP BY tax_rate
                ORDER BY tax_rate
            """.format(where=where), params_u)
            unverified_rows = cursor.fetchall()
            unverified = []
            for row in unverified_rows:
                unverified.append({
                    'tax_rate': row[0],
                    'cnt': row[1],
                    'total_price': round(row[2], 2),
                    'total_tax': round(row[3], 2),
                    'total_amount': round(row[4], 2)
                })

            cursor.execute("""
                SELECT COUNT(*), COALESCE(SUM(tax_amount), 0)
                FROM records
                {where} AND deduction_status = 'certified'
            """.format(where=where), params_c)
            cert_summary = cursor.fetchone()

            cursor.execute("""
                SELECT COUNT(*), COALESCE(SUM(tax_amount), 0)
                FROM records
                {where} AND deduction_status = 'unverified'
            """.format(where=where), params_u)
            unv_summary = cursor.fetchone()

            return {
                'period': period_label,
                'certified': certified,
                'unverified': unverified,
                'certified_summary': {
                    'cnt': cert_summary[0],
                    'total_tax': round(cert_summary[1], 2)
                },
                'unverified_summary': {
                    'cnt': unv_summary[0],
                    'total_tax': round(unv_summary[1], 2)
                }
            }
