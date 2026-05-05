import json
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

HIGH_AMOUNT_THRESHOLD = 10000
SPLIT_SUSPICION_WINDOW_DAYS = 30
SPLIT_SUSPICION_COUNT = 3

RISK_FLAG_LABELS = {
    'high_amount': '大额预警：单张发票价税合计超过 ¥{:,.0f}'.format(HIGH_AMOUNT_THRESHOLD),
    'split_suspicion': '拆票预警：同一销售方{:d}天内存在{:d}张以上相同金额发票'.format(SPLIT_SUSPICION_WINDOW_DAYS, SPLIT_SUSPICION_COUNT),
}


def run_risk_check(invoice, db_manager):
    flags = []

    total_amount = invoice.get('total_amount', 0)
    try:
        total_amount = float(total_amount)
    except (TypeError, ValueError):
        total_amount = 0

    if total_amount > HIGH_AMOUNT_THRESHOLD:
        flags.append('high_amount')
        logger.info(f"风险拦截-大额预警: {invoice.get('invoice_num')} 金额={total_amount}")

    seller_tax_id = invoice.get('seller_tax_id', '')
    if seller_tax_id:
        try:
            split_flag = _check_split_suspicion(invoice, db_manager)
            if split_flag:
                flags.append('split_suspicion')
        except Exception as e:
            logger.warning(f"拆票检查异常: {e}")

    risk_flags_str = ','.join(flags) if flags else ''
    if flags:
        logger.info(f"风险拦截结果: {invoice.get('invoice_num')} flags={flags}")
    return risk_flags_str


def _check_split_suspicion(invoice, db_manager):
    seller_tax_id = invoice.get('seller_tax_id', '')
    total_amount = invoice.get('total_amount', 0)
    invoice_num = invoice.get('invoice_num', '')

    try:
        total_amount = float(total_amount)
    except (TypeError, ValueError):
        return False

    if total_amount <= 0:
        return False

    cutoff_date = (datetime.now() - timedelta(days=SPLIT_SUSPICION_WINDOW_DAYS)).strftime('%Y-%m-%d')

    with db_manager.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM records
            WHERE seller_tax_id = ?
              AND total_amount = ?
              AND date >= ?
              AND invoice_num != ?
        """, (seller_tax_id, total_amount, cutoff_date, invoice_num))
        count = cursor.fetchone()[0]

    if count >= SPLIT_SUSPICION_COUNT:
        logger.info(f"拆票预警: 税号={seller_tax_id}, 金额={total_amount}, 近{SPLIT_SUSPICION_WINDOW_DAYS}天同金额={count}张")
        return True
    return False


def get_risk_flag_labels(risk_flags_str):
    if not risk_flags_str:
        return []
    flags = [f.strip() for f in risk_flags_str.split(',') if f.strip()]
    return [RISK_FLAG_LABELS.get(f, f) for f in flags]
