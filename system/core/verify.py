import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

VERIFY_STATUS_UNVERIFIED = 'unverified'
VERIFY_STATUS_SUCCESS = 'success'
VERIFY_STATUS_FAILED = 'failed'
VERIFY_STATUS_VOIDED = 'voided'
VERIFY_STATUS_RED = 'red'

VALID_VERIFY_STATUSES = {
    VERIFY_STATUS_UNVERIFIED, VERIFY_STATUS_SUCCESS,
    VERIFY_STATUS_FAILED, VERIFY_STATUS_VOIDED, VERIFY_STATUS_RED
}

VERIFY_STATUS_LABELS = {
    'unverified': '待查验',
    'success': '查验通过',
    'failed': '查验失败',
    'voided': '已作废',
    'red': '红冲发票',
}


def verify_invoice_mock(invoice_data):
    result = {
        'status': VERIFY_STATUS_UNVERIFIED,
        'message': '功能待开通',
        'detail': None
    }
    logger.info(
        f"验真Mock: 发票 {invoice_data.get('invoice_num', '未知')} - {result['message']}"
    )
    return result


def format_verify_result(verify_result):
    if not verify_result:
        return ''
    if isinstance(verify_result, dict):
        return json.dumps(verify_result, ensure_ascii=False)
    return str(verify_result)
