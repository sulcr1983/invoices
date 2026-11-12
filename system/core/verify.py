import json
import logging
import re
from datetime import datetime

import requests

from .baidu_ocr import get_baidu_access_token

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

INVOICE_TYPE_MAP = {
    '增值税专用发票': '0',
    '增值税电子专用发票': '0',
    '增值税普通发票': '1',
    '增值税电子普通发票': '1',
    '增值税普通发票（卷式）': '2',
    '通行费增值税电子普通发票': '3',
    '货物运输业增值税专用发票': '4',
    '机动车销售统一发票': '5',
    '二手车销售统一发票': '6',
    '区块链电子发票': '7',
    '全电发票（专用发票）': '8',
    '全电发票（普通发票）': '8',
    '电子发票（航空运输电子客票行程单）': '9',
    '电子发票（铁路电子客票）': '10',
}

VERIFY_API_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/vat_invoice_verification"


def _map_invoice_type(invoice_type_str, invoice_num=''):
    """把发票类型文本映射为百度验真的类型码。

    返回 '' 表示无法判断——此时调用方不应上传该参数，
    而不是像以前那样默认按专票('0')上报（这是历史 11/11 验真失败的直接原因）。
    """
    if invoice_type_str:
        for key, code in INVOICE_TYPE_MAP.items():
            if key in invoice_type_str:
                return code
        if '专' in invoice_type_str:
            return '0'
        if '普' in invoice_type_str:
            return '1'
    # 数电票（全电发票）号码为 20 位，无发票代码
    if invoice_num and len(re.sub(r'\D', '', invoice_num)) == 20:
        return '8'
    return ''


def _format_invoice_date(date_str):
    if not date_str:
        return ''
    cleaned = re.sub(r'[-/年月日]', '', date_str)
    if len(cleaned) >= 8:
        return cleaned[:8]
    return date_str


def _extract_check_code_suffix(check_code, length=6):
    if not check_code:
        return ''
    digits = re.sub(r'\D', '', check_code)
    return digits[-length:] if len(digits) >= length else digits


def verify_invoice_baidu(invoice_data):
    """调用百度验真服务核对单张发票，并返回适合前端展示的查验结果。"""
    access_token = get_baidu_access_token()
    if not access_token:
        return {
            'status': VERIFY_STATUS_FAILED,
            'message': '验真服务还没配置好，请先填写接口信息',
            'detail': None
        }

    invoice_code = invoice_data.get('invoice_code', '')
    invoice_num = invoice_data.get('invoice_num', '')
    invoice_date = _format_invoice_date(invoice_data.get('date', ''))
    check_code = _extract_check_code_suffix(invoice_data.get('check_code', ''))
    invoice_type = _map_invoice_type(invoice_data.get('invoice_type', ''), invoice_num)
    # 百度验真要求的是「价税合计」，此前误传了不含税金额
    total_amount = str(invoice_data.get('total_amount', ''))

    if not invoice_num:
        return {
            'status': VERIFY_STATUS_FAILED,
            'message': '发票号码为空，无法验真',
            'detail': None
        }

    params = {
        'invoice_code': invoice_code,
        'invoice_num': invoice_num,
        'invoice_date': invoice_date,
        'check_code': check_code,
        'total_amount': total_amount,
    }
    # 类型无法判断时不传该参数，避免 invalid parameter invoice_type
    if invoice_type:
        params['invoice_type'] = invoice_type

    url = f"{VERIFY_API_URL}?access_token={access_token}"
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}

    try:
        logger.info(f"百度验真请求: 发票号码={invoice_num}, 类型={invoice_type}")
        response = requests.post(url, data=params, headers=headers, timeout=30)

        if response.status_code != 200:
            logger.error(f"百度验真HTTP错误: {response.status_code}")
            return {
                'status': VERIFY_STATUS_FAILED,
                'message': '验真服务暂时不可用，请稍后重试',
                'detail': None
            }

        result = response.json()

        if 'error_code' in result:
            error_code = result.get('error_code')
            error_msg = result.get('error_msg', '未知错误')
            logger.error(f"百度验真API错误: code={error_code}, msg={error_msg}")
            return {
                'status': VERIFY_STATUS_FAILED,
                'message': '验真失败，请核对发票信息后重试',
                'detail': result
            }

        words_result = result.get('words_result', result)
        verify_result_code = str(words_result.get('VerifyResult', ''))
        verify_message = words_result.get('VerifyMessage', '')
        invalid_sign = words_result.get('InvalidSign', 'N')

        if verify_result_code == '0001':
            if invalid_sign == 'Y':
                status = VERIFY_STATUS_VOIDED
                message = '查验成功：该发票已作废'
            else:
                status = VERIFY_STATUS_SUCCESS
                message = verify_message or '查验成功，发票一致'
        elif verify_result_code == '0000':
            status = VERIFY_STATUS_FAILED
            message = verify_message or '查验失败，发票信息不一致'
        else:
            status = VERIFY_STATUS_FAILED
            message = verify_message or '查验结果暂时无法确认，请稍后重试'

        logger.info(f"百度验真结果: {invoice_num} -> {status} / {message}")
        return {
            'status': status,
            'message': message,
            'detail': words_result
        }

    except requests.Timeout:
        logger.error(f"百度验真超时: {invoice_num}")
        return {
            'status': VERIFY_STATUS_FAILED,
            'message': '验真请求超时，请稍后重试',
            'detail': None
        }
    except Exception as e:
        logger.error(f"百度验真异常: {invoice_num}, 错误: {e}")
        return {
            'status': VERIFY_STATUS_FAILED,
            'message': '验真服务暂时不可用，请稍后重试',
            'detail': None
        }


def verify_invoice_mock(invoice_data):
    """在未启用正式验真时返回待查验状态。"""
    return {
        'status': VERIFY_STATUS_UNVERIFIED,
        'message': '功能待开通',
        'detail': None
    }


def is_verify_available():
    try:
        from ..config import BAIDU_API_KEY, BAIDU_SECRET_KEY
        return bool(BAIDU_API_KEY and BAIDU_SECRET_KEY)
    except (ImportError, AttributeError):
        return False


def format_verify_result(verify_result):
    if not verify_result:
        return ''
    if isinstance(verify_result, dict):
        return json.dumps(verify_result, ensure_ascii=False)
    return str(verify_result)
