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
            return row

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
                period_label = (date_from or '') + '~' + (date_to or '')
            else:
                if not period:
                    period = datetime.now().strftime("%Y-%m")
                where = "WHERE invoice_type LIKE '%专%' AND strftime('%Y-%m', date) = ?"
                params_c = [period]
                params_u = [period]
                period_label = period

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
