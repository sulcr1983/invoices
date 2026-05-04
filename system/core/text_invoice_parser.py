import re
import logging
import os
import sys
from datetime import datetime
if not os.path.dirname(os.path.abspath(__file__)) in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if not os.path.dirname(os.path.dirname(os.path.abspath(__file__))) in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from ..config import INVOICE_TEMPLATE
    from .data_utils import (
        clean_amount, clean_date, clean_seller_name, safe_get_field, is_valid_date
    )
except ImportError:
    from config import INVOICE_TEMPLATE
    from core.data_utils import (
        clean_amount, clean_date, clean_seller_name, safe_get_field, is_valid_date
    )

logger = logging.getLogger(__name__)


def parse_invoice_text_fallback(text, file_path):
    record = {k: v if v != "" else "" for k, v in INVOICE_TEMPLATE.items()}

    lines = text.split('\n')
    is_railway = "铁路" in text or "客票" in text

    def get_lines_around(keywords, max_lines=5):
        positions = []
        for i, line in enumerate(lines):
            for keyword in keywords:
                if keyword in line:
                    positions.append(i)
        all_matched_lines = []
        for pos in positions:
            start = max(0, pos)
            end = min(len(lines), pos + max_lines + 1)
            all_matched_lines.extend(lines[start:end])
        return all_matched_lines

    def extract_from_region(region_lines, patterns):
        region_text = '\n'.join(region_lines)
        for pattern in patterns:
            match = re.search(pattern, region_text)
            if match:
                return match.group(1)
        return ""

    def clean_extracted_text(text):
        if not text:
            return text
        text = re.sub(r'^(名称|销售方|购买方|单位|公司|统一社会信用代码)[:：]\s*', '', text)
        text = re.sub(r'[￥¥,，]', '', text)
        return text.strip()

    def extract_amount_strategy_a(text):
        patterns = [
            r'价税合计\s*（小写）[：:]?\s*([\d,]+\.?\d*)',
            r'价税合计[：:]?\s*([\d,]+\.?\d*)',
            r'（小写）[：:]?\s*([\d,]+\.?\d*)',
            r'小写[：:]?\s*([\d,]+\.?\d*)',
            r'合计[：:]?\s*([\d,]+\.?\d*)'
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return None

    def extract_amount_strategy_b(text):
        all_numbers = []
        for line in lines:
            numbers = re.findall(r'([\d,]+\.\d{2})', line)
            for num_str in numbers:
                num_str_clean = num_str.replace(',', '')
                try:
                    num = float(num_str_clean)
                    if num > 0:
                        all_numbers.append(num)
                except:
                    pass
        if all_numbers:
            return str(max(all_numbers))
        return None

    def extract_amount(text):
        amount_str = extract_amount_strategy_a(text)
        if not amount_str:
            amount_str = extract_amount_strategy_b(text)
        return clean_amount(amount_str)

    def find_date_in_text(text):
        patterns = [
            r'(\d{4})年(\d{1,2})月(\d{1,2})日',
            r'(\d{4})-(\d{1,2})-(\d{1,2})',
            r'(\d{4})/(\d{1,2})/(\d{1,2})',
            r'(\d{8})',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                result = clean_date(match.group(0))
                if result:
                    return result
        return ""

    invoice_num = safe_get_field(text, r'发票号码[：:]\s*([A-Z0-9]+)', 1)
    if not invoice_num:
        invoice_num = safe_get_field(text, r'No\.?\s*([A-Z0-9]+)', 1)
    record['invoice_num'] = invoice_num
    record['invoice_code'] = safe_get_field(text, r'发票代码[：:]\s*([0-9]{10,12})', 1)

    date_str = safe_get_field(text, r'开票日期[：:]\s*(\d{4}[年\-/]\d{1,2}[月\-/]\d{1,2})', 1)
    if not date_str:
        date_str = safe_get_field(text, r'开票时间[：:]\s*(\d{4}[年\-/]\d{1,2}[月\-/]\d{1,2})', 1)
    if not date_str:
        m = re.search(r'(\d{4})[年\-/](\d{2})[月\-/](\d{2})', text)
        if m:
            date_str = m.group(0)
    record['date'] = clean_date(date_str) if date_str else find_date_in_text(text)

    if is_railway:
        seller = safe_get_field(text, r'铁路电子客票.*?(?:发售|开点|售)\s*([^\n]{2,30}?)(?:公司|车站|段|局)', 1)
        if not seller:
            seller = safe_get_field(text, r'(?:出发|发站|售)\s*([^\n]{2,20}?)(?:公司|车站)', 1)
        record['seller'] = clean_seller_name(seller)
    else:
        seller_region = get_lines_around(['销售方', '收款人'])
        seller = extract_from_region(seller_region, [
            r'销售方[名称]?[：:]\s*([^\n]{2,30}?)(?:纳税人|&)',
            r'销售方[：:]\s*([^\n]{2,30})',
            r'名称[：:]\s*([^\n]{2,30})',
        ])
        if not seller:
            seller = safe_get_field(text, r'(?:销售方|卖方|Seller)[：:]\s*([^\n]{2,30})', 1)
        record['seller'] = clean_seller_name(clean_extracted_text(seller)) or "未知单位"

    buyer_region = get_lines_around(['购买方', '付款人'])
    buyer = extract_from_region(buyer_region, [
        r'购买方[名称]?[：:]\s*([^\n]{2,30}?)(?:纳税人|&)',
        r'购买方[：:]\s*([^\n]{2,30})',
    ])
    if not buyer:
        buyer = safe_get_field(text, r'(?:购买方|买方|Buyer)[：:]\s*([^\n]{2,30})', 1)
    record['buyer'] = clean_extracted_text(buyer)

    record['seller_tax_id'] = safe_get_field(text, r'销售方纳税人识别号[：:]\s*([A-Z0-9]{18,20})', 1)
    if not record['seller_tax_id']:
        record['seller_tax_id'] = safe_get_field(text, r'统一社会信用代码[：:]\s*([A-Z0-9]{18,20})', 1)
    record['buyer_tax_id'] = safe_get_field(text, r'购买方纳税人识别号[：:]\s*([A-Z0-9]{18,20})', 1)
    if not record['buyer_tax_id']:
        record['buyer_tax_id'] = safe_get_field(text, r'统一社会信用代码[：:]\s*([A-Z0-9]{18,20})', 1)

    if is_railway:
        item = safe_get_field(text, r'(?:行程|区|路线|出发地|目的地|径路)[：:\s]*([^\n]{3,30})', 1)
        if not item:
            from_match = re.search(r'出发[地站：:\s]*([^\n\s]{2,10})', text)
            to_match = re.search(r'(?:到达|目的)[地站：:\s]*([^\n\s]{2,10})', text)
            if from_match and to_match:
                item = f"{from_match.group(1)}→{to_match.group(1)}"
        record['item'] = item
    else:
        item = safe_get_field(text, r'(?:项目|服务|商品|内容)[：:]\s*([^\n]{3,50})', 1)
        if not item:
            item = safe_get_field(text, r'(?:名称|名目)[：:]\s*([^\n]{3,50})', 1)
        record['item'] = item

    record['total_amount'] = extract_amount(text)

    tax_rate = safe_get_field(text, r'税率[：:]\s*([\d.]+%)', 1)
    if not tax_rate:
        tax_rate = safe_get_field(text, r'税率[：:]\s*([\d.]+)', 1)
    if tax_rate:
        if '%' not in tax_rate and float(tax_rate) > 1:
            tax_rate = str(float(tax_rate) / 100) + '%'
        record['tax_rate'] = tax_rate if '%' in tax_rate else f"{tax_rate}%"

    tax_amount_str = safe_get_field(text, r'税额[：:￥¥]?\s*(?:CNY)?\s*([\d,]+\.?\d*)', 1)
    record['tax_amount'] = clean_amount(tax_amount_str)

    price_str = safe_get_field(text, r'(?:不含税金额|金额|单价|票价)[：:￥¥]?\s*(?:CNY)?\s*([\d,]+\.?\d*)', 1)
    record['price_without_tax'] = clean_amount(price_str)
    if record.get('total_amount') and record.get('tax_amount'):
        calculated_price = record.get('total_amount', 0) - record.get('tax_amount', 0)
        if calculated_price > 0:
            record['price_without_tax'] = round(calculated_price, 2)

    record['check_code'] = safe_get_field(text, r'校验码[：:]\s*([A-Z0-9]{20,50})', 1)
    logger.debug(f"文本解析完成: invoice_num={record.get('invoice_num')}, total_amount={record.get('total_amount')}")
    return record


def validate_invoice(record):
    errors = []
    if not record:
        return False, ["记录为空"]

    invoice_num = record.get('invoice_num', '')
    if not invoice_num or str(invoice_num).strip() == "":
        errors.append("发票号码为空")

    amount = record.get('total_amount', 0)
    try:
        amount = float(amount)
        if amount <= 0:
            errors.append(f"金额必须大于0，当前值: {amount}")
    except (ValueError, TypeError):
        errors.append(f"金额不是有效数字: {amount}")

    date_str = record.get('date', '')
    if not date_str:
        errors.append("开票日期为空")
    elif not is_valid_date(date_str):
        errors.append(f"开票日期格式无效: {date_str}")

    md5 = record.get('file_md5', '')
    if not md5 or str(md5).strip() == "":
        errors.append("文件MD5为空")

    if errors:
        error_msg = "; ".join(errors)
        logger.warning(f"发票数据校验失败: {error_msg}, invoice_num={invoice_num}")
        return False, errors

    return True, []
