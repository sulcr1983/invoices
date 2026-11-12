import logging

from ..webhook_manager import push_to_all_webhooks, compensate_webhooks

logger = logging.getLogger(__name__)


def push_invoice(record, db_manager):
    invoice_num = record.get('invoice_num', '')

    try:
        ok, results = push_to_all_webhooks(record, db_manager)
        if results:
            summary = "; ".join([f"[{r[0]}]{r[1]}={'OK' if r[2] else 'FAIL'}" for r in results])
            logger.info(f"推送完成 [{invoice_num}]: {summary}")
            return ok, results
        else:
            # 未配置任何推送目标：这是"跳过"，不是"成功"，也不是"失败"
            logger.info(f"未配置推送目标，已跳过: {invoice_num}")
            return False, 'skipped'
    except Exception as e:
        logger.error(f"推送异常 [{invoice_num}]: {e}")
        return False, str(e)


def compensate_pending(db_manager):
    try:
        total, ok, fail = compensate_webhooks(db_manager)
        return total, ok, fail
    except Exception as e:
        logger.error(f"补偿机制执行异常: {e}")
        return 0, 0, 0
