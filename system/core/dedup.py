# -*- coding: utf-8 -*-
"""模糊去重：补 MD5 精确匹配的盲区。

同一张发票重新扫描 / 重新下载 / 由不同同事拍摄时，文件指纹会变，
但发票号码、金额、日期高度相似。这里用 RapidFuzz 做二次判定，
把"看起来是同一张票"的记录也拦下来（结果仍写入重复记录台账，可追溯）。
"""

import logging

try:  # RapidFuzz 为可选依赖：缺失时自动退化为只做精确去重
    from rapidfuzz import fuzz
except ImportError:  # pragma: no cover
    fuzz = None

logger = logging.getLogger(__name__)

INVOICE_NUM_THRESHOLD = 90      # 发票号相似度
SELLER_THRESHOLD = 92           # 销售方名称相似度
ITEM_THRESHOLD = 85             # 项目内容相似度
AMOUNT_TOLERANCE = 0.01         # 金额允许误差
DATE_WINDOW_DAYS = 7            # 日期允许前后偏差


def is_available():
    return fuzz is not None


def _norm(text):
    return (text or '').strip().replace(' ', '')


def find_near_duplicate(record, db_manager):
    """返回最相似的既有记录（dict），没有则返回 None。

    只在「金额一致 + 日期相近」的候选集里比较，避免全表扫描。
    """
    if fuzz is None:
        return None

    amount = record.get('total_amount') or 0
    date = (record.get('date') or '')[:10]
    if not date or not amount:
        return None

    try:
        with db_manager.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT invoice_num, seller, item, total_amount, date
                FROM records
                WHERE ABS(COALESCE(total_amount, 0) - ?) <= ?
                  AND date IS NOT NULL AND date != ''
                  AND date >= date(?, '-%d day')
                  AND date <= date(?, '+%d day')
                LIMIT 50
            """ % (DATE_WINDOW_DAYS, DATE_WINDOW_DAYS), (amount, AMOUNT_TOLERANCE, date, date))
            candidates = cursor.fetchall()
    except Exception as e:
        logger.warning(f"模糊去重候选查询失败，跳过: {e}")
        return None

    if not candidates:
        return None

    new_num = _norm(record.get('invoice_num'))
    new_seller = _norm(record.get('seller'))
    new_item = _norm(record.get('item'))

    best = None
    best_score = 0.0
    for inv_num, seller, item, total_amount, inv_date in candidates:
        num_score = fuzz.ratio(new_num, _norm(inv_num)) if new_num and inv_num else 0
        seller_score = fuzz.ratio(new_seller, _norm(seller)) if new_seller and seller else 0
        item_score = fuzz.ratio(new_item, _norm(item)) if new_item and item else 0

        # 发票号高度相似即判定重复；否则要求「销售方 + 项目」同时高度相似
        hit = num_score >= INVOICE_NUM_THRESHOLD or (
            seller_score >= SELLER_THRESHOLD and item_score >= ITEM_THRESHOLD
        )
        score = max(num_score, (seller_score + item_score) / 2)
        if hit and score > best_score:
            best_score = score
            best = {
                'invoice_num': inv_num,
                'seller': seller,
                'item': item,
                'total_amount': total_amount,
                'date': inv_date,
                'score': round(score, 1),
            }

    if best:
        logger.warning(
            f"疑似重复发票（模糊匹配 {best['score']}）: 新={record.get('invoice_num')} "
            f"既有={best['invoice_num']}"
        )
    return best
