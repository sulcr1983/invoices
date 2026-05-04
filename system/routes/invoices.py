from flask import Blueprint, request
from datetime import datetime, timedelta

from .shared import db_manager, api_error

invoices_bp = Blueprint('invoices', __name__)


@invoices_bp.route('/api/invoices', methods=['GET'])
def get_invoices():
    try:
        keyword = request.args.get('keyword')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        seller = request.args.get('seller')
        amt_from = request.args.get('amt_from')
        amt_to = request.args.get('amt_to')
        invoice_type = request.args.get('invoice_type')
        tax_rate = request.args.get('tax_rate')
        push_status = request.args.get('push_status')
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 10))
        offset = (page - 1) * limit

        records, total = db_manager.query_records(
            keyword=keyword, date_from=date_from, date_to=date_to,
            seller=seller, amt_from=amt_from, amt_to=amt_to,
            invoice_type=invoice_type, tax_rate=tax_rate,
            push_status=push_status,
            limit=limit, offset=offset
        )

        invoices = []
        for record in records:
            inv = {
                'invoice_num': record.get('invoice_num'),
                'seller': record.get('seller'),
                'seller_tax_id': record.get('seller_tax_id'),
                'date': record.get('date'),
                'buyer': record.get('buyer'),
                'total_amount': record.get('total_amount'),
                'remark': record.get('remark'),
                'invoice_type': record.get('invoice_type'),
                'deduction_status': None,
                'deduction_deadline': None,
                'days_remaining': None
            }
            inv_date = record.get('date', '')
            inv_type = record.get('invoice_type', '')
            if inv_date and '专' in inv_type:
                try:
                    d = datetime.strptime(inv_date, '%Y-%m-%d')
                    deadline = d + timedelta(days=360)
                    inv['deduction_deadline'] = deadline.strftime('%Y-%m-%d')
                    remaining = (deadline - datetime.now()).days
                    inv['days_remaining'] = remaining
                    if remaining < 0:
                        inv['deduction_status'] = 'expired'
                    elif remaining <= 30:
                        inv['deduction_status'] = 'expiring'
                    else:
                        inv['deduction_status'] = 'normal'
                except Exception:
                    pass
            invoices.append(inv)

        return {
            'status': 'success',
            'data': {
                'invoices': invoices,
                'total': total,
                'page': page,
                'limit': limit,
                'pages': (total + limit - 1) // limit
            }
        }
    except Exception as e:
        return api_error(str(e))


@invoices_bp.route('/api/export/invoices', methods=['GET'])
def export_invoices():
    try:
        keyword = request.args.get('keyword')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        seller = request.args.get('seller')
        amt_from = request.args.get('amt_from')
        amt_to = request.args.get('amt_to')

        records, total = db_manager.query_records(
            keyword=keyword, date_from=date_from, date_to=date_to,
            seller=seller, amt_from=amt_from, amt_to=amt_to,
            limit=None, offset=0
        )
        return {'status': 'success', 'data': {'invoices': records, 'total': total}}
    except Exception as e:
        return api_error(str(e))


@invoices_bp.route('/api/invoices/duplicates', methods=['GET'])
def get_duplicate_invoices():
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        offset = (page - 1) * limit
        records, total = db_manager.get_duplicate_records(limit=limit, offset=offset)
        dup_stats = db_manager.get_duplicate_stats()
        pages = max(1, (total + limit - 1) // limit)
        return {
            'status': 'success',
            'data': {
                'records': records,
                'total': total,
                'page': page,
                'pages': pages,
                'stats': dup_stats
            }
        }
    except Exception as e:
        return api_error(str(e))


@invoices_bp.route('/api/invoices/<invoice_num>', methods=['GET'])
def get_invoice_detail(invoice_num):
    try:
        record = db_manager.get_record_by_invoice_num(invoice_num)
        if not record:
            return {'status': 'error', 'message': '发票不存在'}, 404
        return {'status': 'success', 'data': record}
    except Exception as e:
        return api_error(str(e))


@invoices_bp.route('/api/invoices/<invoice_num>/remark', methods=['PUT'])
def update_invoice_remark(invoice_num):
    try:
        data = request.get_json()
        remark = data.get('remark')
        success = db_manager.update_remark(invoice_num, remark)
        if not success:
            return {'status': 'error', 'message': '更新失败'}, 400
        return {'status': 'success', 'message': '更新成功'}
    except Exception as e:
        return api_error(str(e))


@invoices_bp.route('/api/sellers', methods=['GET'])
def get_sellers():
    try:
        sellers = db_manager.get_distinct_values('seller')
        return {'status': 'success', 'data': sellers}
    except Exception as e:
        return api_error(str(e))
