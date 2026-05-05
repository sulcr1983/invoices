import re
import logging
import sys
from pathlib import Path

_THIS_DIR = str(Path(__file__).resolve().parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)
_PARENT_DIR = str(Path(__file__).resolve().parent.parent)
if _PARENT_DIR not in sys.path:
    sys.path.insert(0, _PARENT_DIR)

try:
    from ..config import INVOICE_TEMPLATE
    from .data_utils import clean_amount, clean_date, clean_seller_name
except ImportError:
    from config import INVOICE_TEMPLATE
    from core.data_utils import clean_amount, clean_date, clean_seller_name

logger = logging.getLogger(__name__)


def _parse_field_list(field_data):
    result = []
    if isinstance(field_data, list):
        for item in field_data:
            if isinstance(item, dict):
                w = item.get('word', item.get('words', '')).strip()
            else:
                w = str(item).strip()
            if w:
                result.append(w)
    elif isinstance(field_data, dict):
        w = field_data.get('word', field_data.get('words', '')).strip()
        if w:
            result.append(w)
    return result


def _extract_invoice_details(words_result):
    details = []

    commodity_names = words_result.get('CommodityName', [])
    commodity_tax_rates = words_result.get('CommodityTaxRate', [])
    commodity_amounts = words_result.get('CommodityAmount', [])
    commodity_tax_amounts = words_result.get('CommodityTaxAmount', [])

    name_list = _parse_field_list(commodity_names)
    rate_list = _parse_field_list(commodity_tax_rates)
    amount_list = [clean_amount(w) for w in _parse_field_list(commodity_amounts)]
    tax_amount_list = [clean_amount(w) for w in _parse_field_list(commodity_tax_amounts)]

    for r_idx in range(len(rate_list)):
        w = rate_list[r_idx]
        if '%' not in w:
            try:
                rv = float(w)
                if rv < 1:
                    rv *= 100
                rate_list[r_idx] = f"{rv}%"
            except:
                pass

    max_count = max(len(name_list), len(amount_list), len(tax_amount_list))
    if max_count <= 1:
        if name_list:
            details.append({
                'item_name': name_list[0],
                'tax_rate': rate_list[0] if len(rate_list) > 0 else '',
                'amount': amount_list[0] if len(amount_list) > 0 else 0.0,
                'tax_amount': tax_amount_list[0] if len(tax_amount_list) > 0 else 0.0,
            })
    else:
        for i in range(max_count):
            details.append({
                'item_name': name_list[i] if i < len(name_list) else '',
                'tax_rate': rate_list[i] if i < len(rate_list) else '',
                'amount': amount_list[i] if i < len(amount_list) else 0.0,
                'tax_amount': tax_amount_list[i] if i < len(tax_amount_list) else 0.0,
            })

    return details


def map_baidu_vat_result(words_result):
    record = {k: v if v != "" else "" for k, v in INVOICE_TEMPLATE.items()}

    def get_field(field_name):
        field_data = words_result.get(field_name, {})
        if isinstance(field_data, dict):
            return str(field_data.get('words', '')).strip()
        return str(field_data).strip() if field_data else ''

    def get_field_from_array(field_name):
        field_data = words_result.get(field_name, [])
        if isinstance(field_data, list) and len(field_data) > 0:
            words = []
            for item in field_data:
                if isinstance(item, dict) and 'word' in item:
                    word = item['word'].strip()
                    if word:
                        words.append(word)
                elif isinstance(item, str):
                    words.append(item.strip())
            return ', '.join(words) if words else ''
        return get_field(field_name)

    def get_total_amount():
        amount_in_figures = get_field('AmountInFiguers')
        if amount_in_figures and amount_in_figures not in ('0', '0.00'):
            return amount_in_figures
        total_amount = get_field('TotalAmount')
        if total_amount and total_amount not in ('0', '0.00'):
            return total_amount
        return '0.00'

    record['invoice_num'] = get_field('InvoiceNum')
    record['invoice_code'] = get_field('InvoiceCode')
    if not record['invoice_code']:
        record['invoice_code'] = get_field('InvoiceCodeConfirm')

    record['item'] = get_field_from_array('CommodityName')

    date_str = get_field('InvoiceDate')
    record['date'] = clean_date(date_str)
    if not record['date']:
        logger.warning(f"日期解析失败: {date_str}")

    record['seller'] = clean_seller_name(get_field('SellerName'))
    record['seller_tax_id'] = get_field('SellerRegisterNum')
    record['buyer'] = get_field('PurchaserName')
    record['buyer_tax_id'] = get_field('PurchaserRegisterNum')

    total_amount = get_total_amount()
    record['total_amount'] = clean_amount(total_amount)

    tax_rate_str = get_field('TaxRate')
    if not tax_rate_str or tax_rate_str == '0':
        tax_rate_str = get_field_from_array('CommodityTaxRate')

    if tax_rate_str:
        if '%' in tax_rate_str:
            record['tax_rate'] = tax_rate_str
        else:
            try:
                rate_float = float(tax_rate_str)
                if rate_float < 1:
                    rate_float *= 100
                record['tax_rate'] = f"{rate_float}%"
            except:
                record['tax_rate'] = tax_rate_str
    else:
        record['tax_rate'] = "0%"

    record['tax_amount'] = clean_amount(get_field('TotalTax'))

    price_without_tax = get_field('AmountWithoutTax')
    if price_without_tax:
        record['price_without_tax'] = clean_amount(price_without_tax)
    else:
        record['price_without_tax'] = round(record.get('total_amount', 0) - record.get('tax_amount', 0), 2)

    record['check_code'] = get_field('CheckCode')
    if not record['check_code']:
        record['check_code'] = get_field('InvoiceNumConfirm')

    record['invoice_type'] = get_field('InvoiceTypeOrg')
    if not record['invoice_type']:
        record['invoice_type'] = get_field('InvoiceType')
    record['remark'] = get_field('Remarks')

    details = _extract_invoice_details(words_result)

    logger.debug(f"百度发票解析完成: invoice_num={record.get('invoice_num')}, total_amount={record.get('total_amount')}")
    return record, details
