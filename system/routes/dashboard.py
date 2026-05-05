from flask import Blueprint

from .shared import db_manager, api_error

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/api/dashboard', methods=['GET'])
def get_dashboard():
    try:
        from ..services import scan_pending_files, ensure_directories
        from datetime import datetime

        stats = db_manager.get_stats()
        recent_records = db_manager.get_recent_records(limit=10)
        recent_invoices = []
        for record in recent_records:
            recent_invoices.append({
                'invoice_num': record[0],
                'seller': record[1],
                'item': record[2],
                'total_amount': record[3],
                'date': record[4]
            })

        ensure_directories()
        pending_files = scan_pending_files()
        pending_count = len(pending_files)
        failed_count = db_manager.get_failed_count()
        unsynced_count = db_manager.get_unsynced_count()
        archived_count = stats['total_cnt']
        duplicate_count = db_manager.get_duplicate_stats()['total']

        monthly_trend = []
        now = datetime.now()
        for i in range(5, -1, -1):
            m = now.month - i
            y = now.year
            while m <= 0:
                m += 12
                y -= 1
            month_str = f"{y:04d}-{m:02d}"
            conn = db_manager._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*), COALESCE(SUM(total_amount),0) FROM records WHERE strftime('%Y-%m', process_time) = ?", (month_str,))
            row = cursor.fetchone()
            conn.close()
            monthly_trend.append({
                'month': month_str,
                'count': row[0],
                'amount': round(row[1], 2)
            })

        return {
            'status': 'success',
            'data': {
                'stats': {
                    'total_cnt': stats['total_cnt'],
                    'total_amt': stats['total_amt'],
                    'month_cnt': stats['month_cnt'],
                    'month_amt': stats['month_amt']
                },
                'directory_status': {
                    'pending': pending_count,
                    'archived': archived_count,
                    'failed': failed_count,
                    'duplicate': duplicate_count
                },
                'recent_invoices': recent_invoices,
                'monthly_trend': monthly_trend
            }
        }
    except Exception as e:
        return api_error(str(e))
