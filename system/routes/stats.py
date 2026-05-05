from flask import Blueprint, request
from datetime import datetime, timedelta

from .shared import db_manager, api_error

stats_bp = Blueprint('stats', __name__)


@stats_bp.route('/api/stats/summary', methods=['GET'])
def get_stats_summary():
    try:
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        conn = db_manager._get_connection()
        cursor = conn.cursor()

        where = ""
        params = []
        if date_from:
            where += " AND date >= ?"
            params.append(date_from)
        if date_to:
            where += " AND date <= ?"
            params.append(date_to)

        cursor.execute(f"SELECT COUNT(*), COALESCE(SUM(total_amount),0), COALESCE(SUM(price_without_tax),0), COALESCE(SUM(tax_amount),0) FROM records WHERE 1=1 {where}", params)
        row = cursor.fetchone()
        total_cnt = row[0]
        total_amt = round(row[1], 2)
        total_price = round(row[2], 2)
        total_tax = round(row[3], 2)

        cursor.execute(f"SELECT COUNT(DISTINCT seller) FROM records WHERE 1=1 {where}", params)
        seller_cnt = cursor.fetchone()[0]

        cursor.execute(f"SELECT seller, COUNT(*) as cnt, COALESCE(SUM(total_amount),0) as amt FROM records WHERE 1=1 {where} GROUP BY seller ORDER BY amt DESC LIMIT 10", params)
        seller_cols = [desc[0] for desc in cursor.description]
        top_sellers = [dict(zip(seller_cols, r)) for r in cursor.fetchall()]
        for s in top_sellers:
            s['amt'] = round(s['amt'], 2)

        cursor.execute(f"""
            SELECT strftime('%Y-%m', date) as month, COUNT(*) as cnt,
                   COALESCE(SUM(total_amount),0) as amt,
                   COALESCE(SUM(price_without_tax),0) as price,
                   COALESCE(SUM(tax_amount),0) as tax
            FROM records WHERE date IS NOT NULL AND date != '' {where}
            GROUP BY strftime('%Y-%m', date) ORDER BY month DESC LIMIT 12
        """, params)
        month_cols = [desc[0] for desc in cursor.description]
        monthly_summary = [dict(zip(month_cols, r)) for r in cursor.fetchall()]
        for m in monthly_summary:
            m['amt'] = round(m['amt'], 2)
            m['price'] = round(m['price'], 2)
            m['tax'] = round(m['tax'], 2)

        cursor.execute(f"""
            SELECT invoice_type, COUNT(*) as cnt, COALESCE(SUM(total_amount),0) as amt
            FROM records WHERE 1=1 {where} GROUP BY invoice_type ORDER BY cnt DESC
        """, params)
        type_cols = [desc[0] for desc in cursor.description]
        type_summary = [dict(zip(type_cols, r)) for r in cursor.fetchall()]
        for t in type_summary:
            t['amt'] = round(t['amt'], 2)

        conn.close()

        return {
            'status': 'success',
            'data': {
                'total_cnt': total_cnt,
                'total_amt': total_amt,
                'total_price': total_price,
                'total_tax': total_tax,
                'seller_cnt': seller_cnt,
                'top_sellers': top_sellers,
                'monthly_summary': monthly_summary,
                'type_summary': type_summary
            }
        }
    except Exception as e:
        return api_error(str(e))


@stats_bp.route('/api/stats/input-tax-summary', methods=['GET'])
def get_input_tax_summary():
    try:
        period = request.args.get('period')
        result = db_manager.get_input_tax_summary(period)
        return {
            'status': 'success',
            'data': result
        }
    except Exception as e:
        return api_error(str(e))


@stats_bp.route('/api/stats/deduction-alert', methods=['GET'])
def get_deduction_alert():
    try:
        conn = db_manager._get_connection()
        cursor = conn.cursor()
        now = datetime.now()
        cursor.execute("""
            SELECT invoice_num, seller, date, total_amount, invoice_type
            FROM records
            WHERE invoice_type LIKE '%专%' AND date IS NOT NULL AND date != ''
            ORDER BY date ASC
        """)
        col_names = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        expired = []
        expiring = []
        for row in rows:
            rec = dict(zip(col_names, row))
            try:
                d = datetime.strptime(rec['date'], '%Y-%m-%d')
                deadline = d + timedelta(days=360)
                remaining = (deadline - now).days
                rec['deduction_deadline'] = deadline.strftime('%Y-%m-%d')
                rec['days_remaining'] = remaining
                if remaining < 0:
                    expired.append(rec)
                elif remaining <= 30:
                    expiring.append(rec)
            except Exception:
                pass
        conn.close()
        return {
            'status': 'success',
            'data': {
                'expired_count': len(expired),
                'expiring_count': len(expiring),
                'expired': expired[:20],
                'expiring': expiring[:20]
            }
        }
    except Exception as e:
        return api_error(str(e))
