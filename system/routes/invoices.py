from flask import Blueprint, request, send_file
from datetime import datetime, timedelta
from pathlib import Path
import logging
import mimetypes

from .shared import db_manager, api_error
from ..config import ARCHIVE_DIR

logger = logging.getLogger(__name__)

invoices_bp = Blueprint('invoices', __name__)


@invoices_bp.route('/api/invoices', methods=['GET'])
def get_invoices():
    """按筛选、排序和分页条件返回发票台账列表。"""
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
        verify_status = request.args.get('verify_status')
        risk_flags = request.args.get('risk_flags')
        sort_field = request.args.get('sort_field', '')
        sort_dir = request.args.get('sort_dir', 'desc')

        # 分页参数严格校验：非法值返回 400，而不是抛出 500
        try:
            page = int(request.args.get('page', 1))
            limit = int(request.args.get('limit', 10))
        except (TypeError, ValueError):
            return {'status': 'error', 'message': 'page / limit 必须为整数'}, 400
        if page < 1:
            return {'status': 'error', 'message': 'page 必须大于等于 1'}, 400
        if limit < 1 or limit > 200:
            return {'status': 'error', 'message': 'limit 必须在 1-200 之间'}, 400
        offset = (page - 1) * limit

        order_by_map = {'date': 'date', 'amount': 'total_amount'}
        order_by = order_by_map.get(sort_field, 'process_time')
        order_dir = 'ASC' if sort_dir == 'asc' else 'DESC'

        records, total = db_manager.query_records(
            keyword=keyword, date_from=date_from, date_to=date_to,
            seller=seller, amt_from=amt_from, amt_to=amt_to,
            invoice_type=invoice_type, tax_rate=tax_rate,
            push_status=push_status, verify_status=verify_status, risk_flags=risk_flags,
            order_by=order_by, order_dir=order_dir,
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
                'verify_status': record.get('verify_status', 'unverified'),
                'deadline_status': None,
                'deduction_deadline': None,
                'days_remaining': None,
                'certification_status': record.get('deduction_status', 'unverified'),
                'certification_date': record.get('certification_date', ''),
                'department': record.get('department', ''),
                'project': record.get('project', ''),
                'expense_type': record.get('expense_type', ''),
                'risk_flags': record.get('risk_flags', '')
            }
            inv_date = record.get('date', '')
            inv_type = record.get('invoice_type', '')
            if inv_date and '专' in inv_type:
                try:
                    d = datetime.strptime(inv_date, '%Y-%m-%d').date()
                    deadline = d + timedelta(days=360)
                    inv['deduction_deadline'] = deadline.strftime('%Y-%m-%d')
                    # 用 date 相减：当天到期不会被算成 -1 天而误判"已过期"
                    remaining = (deadline - datetime.now().date()).days
                    inv['days_remaining'] = remaining
                    if remaining < 0:
                        inv['deadline_status'] = 'expired'
                    elif remaining <= 30:
                        inv['deadline_status'] = 'expiring'
                    else:
                        inv['deadline_status'] = 'normal'
                except (ValueError, TypeError) as e:
                    logger.debug(f"抵扣期限计算跳过 {record.get('invoice_num')}: {e}")
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


@invoices_bp.route('/api/invoices/batch-certify', methods=['POST'])
def batch_certify_invoices():
    try:
        data = request.get_json(silent=True) or {}
        invoice_nums = data.get('invoice_nums', [])
        certification_date = data.get('certification_date')

        if not invoice_nums or not isinstance(invoice_nums, list):
            return {'status': 'error', 'message': '请提供发票号码列表'}, 400

        updated = db_manager.batch_update_deduction_status(
            invoice_nums, 'certified', certification_date
        )
        return {
            'status': 'success',
            'data': {
                'updated': updated,
                'total': len(invoice_nums)
            },
            'message': f'成功认证 {updated} 张发票'
        }
    except Exception as e:
        return api_error(str(e))


@invoices_bp.route('/api/invoices/batch-verify', methods=['POST'])
def batch_verify_invoices():
    """批量查验选中的发票，并汇总成功、失败和跳过数量。"""
    try:
        from ..core.verify import (
            verify_invoice_baidu, is_verify_available, format_verify_result
        )
        from ..config import VERIFY_ENABLED, VERIFY_COST_PER_CALL

        data = request.get_json(silent=True) or {}
        invoice_nums = data.get('invoice_nums', [])

        if not invoice_nums or not isinstance(invoice_nums, list):
            return {'status': 'error', 'message': '请提供发票号码列表'}, 400

        if not VERIFY_ENABLED:
            return {'status': 'error', 'message': '验真功能还没有打开，请先在设置文件中启用'}, 403

        if not is_verify_available():
            return {'status': 'error', 'message': '验真服务还没配置好，请先填写百度接口信息'}, 403

        results = []
        success_count = 0
        fail_count = 0
        skip_count = 0
        total_cost = 0

        for invoice_num in invoice_nums:
            record = db_manager.get_record_by_invoice_num(invoice_num)
            if not record:
                results.append({
                    'invoice_num': invoice_num,
                    'status': 'error',
                    'message': '发票不存在'
                })
                fail_count += 1
                continue

            if record.get('verify_status') not in ('unverified', '', None):
                results.append({
                    'invoice_num': invoice_num,
                    'verify_status': record.get('verify_status'),
                    'message': '已查验，跳过',
                    'skipped': True
                })
                skip_count += 1
                continue

            result = verify_invoice_baidu(record)
            db_manager.update_verify_status(
                invoice_num,
                result.get('status'),
                format_verify_result(result)
            )

            is_ok = result.get('status') == 'success'
            results.append({
                'invoice_num': invoice_num,
                'verify_status': result.get('status'),
                'message': result.get('message', ''),
                'skipped': False
            })
            if is_ok:
                success_count += 1
            else:
                fail_count += 1
            # 只有真正发出并拿到接口响应（detail 非空）才计费；
            # 参数错误/未配置等本地失败不应计费。
            if result.get('detail') is not None:
                total_cost += VERIFY_COST_PER_CALL

        return {
            'status': 'success',
            'data': {
                'results': results,
                'total': len(invoice_nums),
                'success': success_count,
                'failed': fail_count,
                'skipped': skip_count,
                'total_cost': round(total_cost, 2)
            },
            'message': f'验真完成：成功 {success_count} 张，失败 {fail_count} 张，跳过 {skip_count} 张'
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


@invoices_bp.route('/api/invoices/<invoice_num>/original', methods=['GET'])
def get_invoice_original(invoice_num):
    try:
        archive_root = Path(ARCHIVE_DIR)
        if not archive_root.exists():
            return {'status': 'error', 'message': '归档目录不存在'}, 404
        for year_dir in sorted(archive_root.iterdir(), reverse=True):
            if not year_dir.is_dir():
                continue
            for month_dir in sorted(year_dir.iterdir(), reverse=True):
                if not month_dir.is_dir():
                    continue
                for fp in month_dir.iterdir():
                    # 精确匹配 _<发票号> 结尾，避免 1234 命中 12345
                    if fp.is_file() and fp.stem.endswith('_' + invoice_num):
                        mime, _ = mimetypes.guess_type(str(fp))
                        return send_file(str(fp), mimetype=mime or 'application/octet-stream')
        return {'status': 'error', 'message': '原图未找到'}, 404
    except Exception as e:
        return api_error(str(e))


@invoices_bp.route('/api/invoices/<invoice_num>/remark', methods=['PUT'])
def update_invoice_remark(invoice_num):
    try:
        data = request.get_json(silent=True) or {}
        remark = data.get('remark')
        success = db_manager.update_remark(invoice_num, remark)
        if not success:
            return {'status': 'error', 'message': '更新失败'}, 400
        return {'status': 'success', 'message': '更新成功'}
    except Exception as e:
        return api_error(str(e))


@invoices_bp.route('/api/invoices/<invoice_num>/attribution', methods=['PUT'])
def update_invoice_attribution(invoice_num):
    try:
        data = request.get_json(silent=True) or {}
        department = data.get('department')
        project = data.get('project')
        expense_type = data.get('expense_type')
        success = db_manager.update_expense_attribution(
            invoice_num, department=department, project=project, expense_type=expense_type
        )
        if not success:
            return {'status': 'error', 'message': '更新失败'}, 400
        return {'status': 'success', 'message': '费用归属更新成功'}
    except Exception as e:
        return api_error(str(e))


@invoices_bp.route('/api/sellers', methods=['GET'])
def get_sellers():
    try:
        sellers = db_manager.get_distinct_values('seller')
        return {'status': 'success', 'data': sellers}
    except Exception as e:
        return api_error(str(e))


@invoices_bp.route('/api/invoices/<invoice_num>/verify', methods=['POST'])
def verify_single_invoice(invoice_num):
    """查验单张发票，已查验过的发票直接返回现有状态。"""
    try:
        from ..core.verify import (
            verify_invoice_baidu,
            is_verify_available, format_verify_result,
            VERIFY_STATUS_LABELS
        )
        from ..config import VERIFY_ENABLED, VERIFY_COST_PER_CALL

        record = db_manager.get_record_by_invoice_num(invoice_num)
        if not record:
            return {'status': 'error', 'message': '发票不存在'}, 404

        if record.get('verify_status') not in ('unverified', '', None):
            return {
                'status': 'success',
                'data': {
                    'invoice_num': invoice_num,
                    'verify_status': record.get('verify_status'),
                    'verify_message': VERIFY_STATUS_LABELS.get(record.get('verify_status'), '已查验'),
                    'already_verified': True
                }
            }

        if not VERIFY_ENABLED:
            return {
                'status': 'error',
                'message': '验真功能还没有打开，请先在设置文件中启用',
            }, 403

        if not is_verify_available():
            return {
                'status': 'error',
                'message': '验真服务还没配置好，请先填写百度接口信息',
            }, 403

        result = verify_invoice_baidu(record)

        db_manager.update_verify_status(
            invoice_num,
            result.get('status'),
            format_verify_result(result)
        )

        return {
            'status': 'success',
            'data': {
                'invoice_num': invoice_num,
                'verify_status': result.get('status'),
                'verify_message': result.get('message', ''),
                'already_verified': False,
                # 本地参数错误/未配置不应计费
                'cost': VERIFY_COST_PER_CALL if result.get('detail') is not None else 0
            }
        }
    except Exception as e:
        return api_error(str(e))


@invoices_bp.route('/api/verify/config', methods=['GET'])
def get_verify_config():
    try:
        from ..core.verify import is_verify_available
        from ..config import VERIFY_ENABLED, VERIFY_COST_PER_CALL
        return {
            'status': 'success',
            'data': {
                'enabled': VERIFY_ENABLED,
                'available': is_verify_available(),
                'cost_per_call': VERIFY_COST_PER_CALL
            }
        }
    except Exception as e:
        return api_error(str(e))
