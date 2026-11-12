from flask import Blueprint, request

from .shared import db_manager, api_error

stats_bp = Blueprint('stats', __name__)


def _date_filter():
    """统一解析日期区间条件，返回 (where 片段, 参数列表)。"""
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    where = ""
    params = []
    if date_from:
        where += " AND date >= ?"
        params.append(date_from)
    if date_to:
        where += " AND date <= ?"
        params.append(date_to)
    return where, params


@stats_bp.route('/api/stats/summary', methods=['GET'])
def get_stats_summary():
    try:
        where, params = _date_filter()
        # with 语句保证任何分支/异常都会关闭连接（原实现异常时连接泄漏）
        with db_manager.connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                f"SELECT COUNT(*), COALESCE(SUM(total_amount),0), "
                f"COALESCE(SUM(price_without_tax),0), COALESCE(SUM(tax_amount),0) "
                f"FROM records WHERE 1=1 {where}", params)
            row = cursor.fetchone()
            total_cnt = row[0]
            total_amt = round(row[1], 2)
            total_price = round(row[2], 2)
            total_tax = round(row[3], 2)

            cursor.execute(f"SELECT COUNT(DISTINCT seller) FROM records WHERE 1=1 {where}", params)
            seller_cnt = cursor.fetchone()[0]

            cursor.execute(
                f"SELECT seller, COUNT(*) as cnt, COALESCE(SUM(total_amount),0) as amt "
                f"FROM records WHERE 1=1 {where} GROUP BY seller ORDER BY amt DESC LIMIT 5", params)
            seller_cols = [desc[0] for desc in cursor.description]
            top_sellers = [dict(zip(seller_cols, r)) for r in cursor.fetchall()]
            for s in top_sellers:
                s['amt'] = round(s['amt'], 2)

            cursor.execute(f"""
                SELECT substr(date, 1, 7) as month, COUNT(*) as cnt,
                       COALESCE(SUM(total_amount),0) as amt,
                       COALESCE(SUM(price_without_tax),0) as price,
                       COALESCE(SUM(tax_amount),0) as tax
                FROM records WHERE date IS NOT NULL AND date != '' AND length(date) >= 7 {where}
                GROUP BY substr(date, 1, 7) ORDER BY month ASC
            """, params)
            month_cols = [desc[0] for desc in cursor.description]
            monthly_summary = [dict(zip(month_cols, r)) for r in cursor.fetchall()]
            for m in monthly_summary:
                m['amt'] = round(m['amt'], 2)
                m['price'] = round(m['price'], 2)
                m['tax'] = round(m['tax'], 2)

            cursor.execute(f"""
                SELECT COALESCE(NULLIF(invoice_type,''), '未识别') as invoice_type,
                       COUNT(*) as cnt, COALESCE(SUM(total_amount),0) as amt
                FROM records WHERE 1=1 {where}
                GROUP BY COALESCE(NULLIF(invoice_type,''), '未识别') ORDER BY cnt DESC
            """, params)
            type_cols = [desc[0] for desc in cursor.description]
            type_summary = [dict(zip(type_cols, r)) for r in cursor.fetchall()]
            for t in type_summary:
                t['amt'] = round(t['amt'], 2)

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


@stats_bp.route('/api/stats/expense-distribution', methods=['GET'])
def get_expense_distribution():
    try:
        where, params = _date_filter()
        with db_manager.connection() as conn:
            cursor = conn.cursor()

            cursor.execute(f"""
                SELECT COALESCE(NULLIF(department, ''), '未分配') as dept,
                       COUNT(*) as cnt,
                       COALESCE(SUM(total_amount), 0) as amt
                FROM records WHERE 1=1 {where}
                GROUP BY dept
                ORDER BY amt DESC
            """, params)
            dept_distribution = [
                {'name': r[0], 'cnt': r[1], 'amt': round(r[2], 2)} for r in cursor.fetchall()
            ]

            cursor.execute(f"""
                SELECT COALESCE(NULLIF(expense_type, ''), '未分类') as exp_type,
                       COUNT(*) as cnt,
                       COALESCE(SUM(total_amount), 0) as amt
                FROM records WHERE 1=1 {where}
                GROUP BY exp_type
                ORDER BY amt DESC
            """, params)
            expense_distribution = [
                {'name': r[0], 'cnt': r[1], 'amt': round(r[2], 2)} for r in cursor.fetchall()
            ]

            # 风险数量与风险列表必须使用同一套日期条件，否则两个口径会打架
            risk_where = where + " AND risk_flags IS NOT NULL AND risk_flags != ''"
            cursor.execute(f"SELECT COUNT(DISTINCT invoice_num) FROM records WHERE 1=1 {risk_where}", params)
            risk_count = cursor.fetchone()[0]

            cursor.execute(f"""
                SELECT invoice_num, seller, total_amount, date, risk_flags
                FROM records WHERE 1=1 {risk_where}
                ORDER BY process_time DESC LIMIT 20
            """, params)
            risk_invoices = []
            seen_nums = set()
            from ..core.risk_checker import get_risk_flag_labels
            for row in cursor.fetchall():
                if row[0] in seen_nums:
                    continue
                seen_nums.add(row[0])
                risk_invoices.append({
                    'invoice_num': row[0],
                    'seller': row[1],
                    'total_amount': row[2],
                    'date': row[3],
                    'risk_flags': row[4],
                    'risk_labels': get_risk_flag_labels(row[4])
                })

        return {
            'status': 'success',
            'data': {
                'dept_distribution': dept_distribution,
                'expense_distribution': expense_distribution,
                'risk_count': risk_count,
                'risk_invoices': risk_invoices
            }
        }
    except Exception as e:
        return api_error(str(e))


@stats_bp.route('/api/stats/input-tax-summary', methods=['GET'])
def get_input_tax_summary():
    try:
        period = request.args.get('period')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        result = db_manager.get_input_tax_summary(period=period, date_from=date_from, date_to=date_to)
        return {
            'status': 'success',
            'data': result
        }
    except Exception as e:
        return api_error(str(e))