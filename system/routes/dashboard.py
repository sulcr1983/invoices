from flask import Blueprint

from .shared import db_manager, api_error

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/api/dashboard', methods=['GET'])
def get_dashboard():
    try:
        from ..services import scan_pending_files, ensure_directories

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
        archived_count = stats['total_cnt']
        duplicate_count = db_manager.get_duplicate_stats()['total']

        # 一次查询拿全，避免"拉 1000 条在浏览器里数"
        status_counts = db_manager.get_status_counts()
        monthly_trend = db_manager.get_monthly_trend(months=6)

        return {
            'status': 'success',
            'data': {
                'stats': {
                    'total_cnt': stats['total_cnt'],
                    'total_amt': stats['total_amt'],
                    'month_cnt': stats['month_cnt'],
                    'month_amt': stats['month_amt']
                },
                'status_counts': status_counts,
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