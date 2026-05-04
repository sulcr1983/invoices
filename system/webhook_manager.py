import asyncio
import requests
import json
import logging
import time
from datetime import datetime
try:
    from .config import REQUEST_TIMEOUT
    from .core.webhook_payload import _str, _amount, _normalize_text, _build_fields, _get_default_for_extra_field
    from .core.webhook_payload import build_wecom_payload, PAYLOAD_BUILDERS, PLATFORM_LABELS
except ImportError:
    from config import REQUEST_TIMEOUT
    from core.webhook_payload import _str, _amount, _normalize_text, _build_fields, _get_default_for_extra_field
    from core.webhook_payload import build_wecom_payload, PAYLOAD_BUILDERS, PLATFORM_LABELS

logger = logging.getLogger(__name__)

RECORD_COLUMNS = [
    'invoice_num', 'seller', 'seller_tax_id',
    'date', 'buyer', 'buyer_tax_id', 'item',
    'price_without_tax', 'tax_rate', 'tax_amount', 'total_amount',
    'invoice_code', 'check_code', 'invoice_type', 'remark',
    'file_md5', 'sync_status', 'push_status',
    'retry_count', 'last_error', 'process_time', 'error_type'
]


def row_to_dict(row):
    return dict(zip(RECORD_COLUMNS, row))


def push_single_webhook(record_dict, webhook, db_manager):
    hook_id = webhook["id"]
    platform = webhook["platform"]
    url = webhook["url"]
    max_retries = webhook.get("max_retries", 3)
    label = PLATFORM_LABELS.get(platform, platform)
    invoice_num = record_dict.get("invoice_num", "")

    builder = PAYLOAD_BUILDERS.get(platform)
    if not builder:
        logger.warning(f"未知平台类型: {platform}，跳过")
        return False

    try:
        if platform == "wecom":
            schema_str = webhook.get("schema_json") or "{}"
            schema = json.loads(schema_str)
            payload = builder(record_dict, schema)
        else:
            payload = builder(record_dict)
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        error_msg = f"payload 构建失败: {e}"
        logger.error(f"[{label}][{invoice_num}] {error_msg}")
        db_manager.add_push_history(invoice_num, hook_id, platform, "failed", error_msg)
        db_manager.update_webhook_push_result(hook_id, "failed", error_msg)
        return False

    logger.debug(f"[{label}][{invoice_num}] 发送: {json.dumps(payload, ensure_ascii=False)[:200]}")

    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                result = resp.json()
                errcode = result.get("errcode", 0)
                if errcode == 0:
                    logger.info(f"[{label}][{invoice_num}] 推送成功 (id={hook_id})")
                    db_manager.add_push_history(invoice_num, hook_id, platform, "success")
                    db_manager.update_webhook_push_result(hook_id, "success")
                    return True
                else:
                    error_msg = f"errcode={errcode}, {result.get('errmsg','')}"
            else:
                error_msg = f"HTTP {resp.status_code}: {resp.text[:100]}"
        except requests.exceptions.Timeout:
            error_msg = "连接超时"
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
        except Exception as e:
            error_msg = f"未知错误: {e}"

        if attempt < max_retries:
            logger.warning(f"[{label}][{invoice_num}] 推送失败(第{attempt}次): {error_msg}")
            time.sleep(2)
        else:
            logger.error(f"[{label}][{invoice_num}] 推送失败(已达最大重试): {error_msg}")
            db_manager.add_push_history(invoice_num, hook_id, platform, "failed", error_msg, retry_num=attempt)
            db_manager.update_webhook_push_result(hook_id, "failed", error_msg)
            return False

    return False


async def async_push_single_webhook(record_dict, webhook, db_manager):
    import aiohttp
    hook_id = webhook["id"]
    platform = webhook["platform"]
    url = webhook["url"]
    max_retries = webhook.get("max_retries", 3)
    label = PLATFORM_LABELS.get(platform, platform)
    invoice_num = record_dict.get("invoice_num", "")

    builder = PAYLOAD_BUILDERS.get(platform)
    if not builder:
        logger.warning(f"未知平台类型: {platform}，跳过")
        return False

    try:
        if platform == "wecom":
            schema_str = webhook.get("schema_json") or "{}"
            schema = json.loads(schema_str)
            payload = builder(record_dict, schema)
        else:
            payload = builder(record_dict)
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        error_msg = f"payload 构建失败: {e}"
        logger.error(f"[{label}][{invoice_num}] {error_msg}")
        db_manager.add_push_history(invoice_num, hook_id, platform, "failed", error_msg)
        db_manager.update_webhook_push_result(hook_id, "failed", error_msg)
        return False

    for attempt in range(1, max_retries + 1):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        errcode = result.get("errcode", 0)
                        if errcode == 0:
                            logger.info(f"[{label}][{invoice_num}] 异步推送成功 (id={hook_id})")
                            db_manager.add_push_history(invoice_num, hook_id, platform, "success")
                            db_manager.update_webhook_push_result(hook_id, "success")
                            return True
                        else:
                            error_msg = f"errcode={errcode}, {result.get('errmsg','')}"
                    else:
                        error_msg = f"HTTP {resp.status}: {resp.text[:100]}"
        except asyncio.TimeoutError:
            error_msg = "连接超时"
        except Exception as e:
            error_msg = str(e)[:80]

        if attempt < max_retries:
            logger.warning(f"[{label}][{invoice_num}] 异步推送失败(第{attempt}次): {error_msg}")
        else:
            logger.error(f"[{label}][{invoice_num}] 异步推送失败(已达最大重试): {error_msg}")
            db_manager.add_push_history(invoice_num, hook_id, platform, "failed", error_msg, retry_num=attempt)
            db_manager.update_webhook_push_result(hook_id, "failed", error_msg)
            return False

    return False


def push_to_all_webhooks(record_dict, db_manager):
    invoice_num = record_dict.get("invoice_num", "")
    webhooks = db_manager.get_all_webhooks(only_enabled=True)

    if not webhooks:
        logger.debug(f"无 webhook 配置，跳过多路推送: {invoice_num}")
        db_manager.update_push_success(invoice_num)
        return True, []

    results = []
    for wh in webhooks:
        ok = push_single_webhook(record_dict, wh, db_manager)
        results.append((wh["platform"], wh["name"], ok))
        time.sleep(0.5)

    any_ok = any(r[2] for r in results)
    summary = "; ".join([f"[{r[0]}]{r[1]}={'OK' if r[2] else 'FAIL'}" for r in results])
    logger.info(f"多路推送完成 [{invoice_num}]: {summary}")

    if any_ok:
        db_manager.update_push_success(invoice_num)
    else:
        current_status, current_retry = db_manager.get_push_status(invoice_num)
        new_retry = (current_retry or 0) + 1
        error_detail = summary[:200]
        db_manager.update_push_failed(invoice_num, new_retry, error_detail, 'webhook_error')

    return any_ok, results


async def async_push_to_all_webhooks(record_dict, db_manager):
    import asyncio
    invoice_num = record_dict.get("invoice_num", "")
    webhooks = db_manager.get_all_webhooks(only_enabled=True)

    if not webhooks:
        logger.debug(f"无 webhook 配置，跳过异步多路推送: {invoice_num}")
        db_manager.update_push_success(invoice_num)
        return True, []

    tasks = []
    for wh in webhooks:
        task = async_push_single_webhook(record_dict, wh, db_manager)
        tasks.append((wh, task))

    # 并行推送
    results_data = []
    for wh, task in tasks:
        ok = await task
        results_data.append((wh["platform"], wh["name"], ok))

    any_ok = any(r[2] for r in results_data)
    summary = "; ".join([f"[{r[0]}]{r[1]}={'OK' if r[2] else 'FAIL'}" for r in results_data])
    logger.info(f"异步多路推送完成 [{invoice_num}]: {summary}")

    if any_ok:
        db_manager.update_push_success(invoice_num)
    else:
        current_status, current_retry = db_manager.get_push_status(invoice_num)
        new_retry = (current_retry or 0) + 1
        error_detail = summary[:200]
        db_manager.update_push_failed(invoice_num, new_retry, error_detail, 'webhook_error')

    return any_ok, results_data


def compensate_webhooks(db_manager):
    logger.info("开始补偿推送...")

    records = db_manager.get_records_for_compensate()
    if not records:
        logger.info("无需补偿的记录")
        return 0, 0, 0

    success_count = 0
    fail_count = 0

    for row in records:
        record_dict = row_to_dict(row)
        invoice_num = record_dict.get("invoice_num", "")
        error_type = record_dict.get("error_type", "")

        if error_type in ("ocr_error", "extract_error", "validation_error", "md5_error"):
            continue

        logger.info(f"补偿推送: {invoice_num}")
        ok, _ = push_to_all_webhooks(record_dict, db_manager)
        if ok:
            success_count += 1
        else:
            fail_count += 1

    total = success_count + fail_count
    logger.info(f"补偿推送完成: 共处理{total}条，成功{success_count}，失败{fail_count}")
    return total, success_count, fail_count


def test_webhook_connection(platform, url, schema_json=None):
    record_dict = {
        "invoice_num": "TEST000001",
        "seller": "测试单位",
        "seller_tax_id": "91110101MA12345678",
        "date": "2026-04-25",
        "buyer": "测试买方",
        "buyer_tax_id": "91110101MA87654321",
        "item": "测试服务",
        "price_without_tax": 100.00,
        "tax_rate": "6%",
        "tax_amount": 6.00,
        "total_amount": 106.00,
        "invoice_code": "123456789012",
        "check_code": "TEST123",
    }

    builder = PAYLOAD_BUILDERS.get(platform)
    if not builder:
        return {"ok": False, "msg": f"未知平台: {platform}"}

    try:
        if platform == "wecom":
            schema = json.loads(schema_json or "{}")
            payload = builder(record_dict, schema)
        else:
            payload = builder(record_dict)
    except (json.JSONDecodeError, ValueError) as e:
        return {"ok": False, "msg": f"Payload构建失败: {e}"}

    try:
        resp = requests.post(url, json=payload, timeout=15)

        if resp.status_code == 200:
            result = resp.json()
            if platform == "wecom":
                errcode = result.get("errcode", -1)
                if errcode == 0:
                    return {"ok": True, "msg": "连接成功！企业微信智能表格 Webhook 配置正确"}
                elif errcode == 2022004:
                    return {"ok": True, "msg": "连接成功！Webhook 地址有效（字段名需在发票数据中配置）"}
                elif errcode == 301002:
                    return {"ok": False, "msg": "无权限：请在企业微信后台开通智能表格权限"}
                elif errcode == 301005:
                    return {"ok": False, "msg": "表格不存在或已被删除"}
                elif errcode == 301013:
                    return {"ok": False, "msg": "字段不匹配：请检查 schema_json 中的字段 ID 是否正确"}
                else:
                    return {"ok": False, "msg": f"企微错误: errcode={errcode}, {result.get('errmsg','')}"}
            else:
                if result.get("errcode") == 0 or result.get("code") == 0:
                    return {"ok": True, "msg": "连接成功"}
                return {"ok": False, "msg": f"未知响应格式: {str(result)[:100]}"}

        elif resp.status_code == 401:
            return {"ok": False, "msg": "认证失败：Webhook Token 或权限无效"}
        elif resp.status_code == 403:
            return {"ok": False, "msg": "权限不足：请检查 Webhook 是否有写入权限"}
        elif resp.status_code == 404:
            return {"ok": False, "msg": "接口不存在：请确认 Webhook 地址是否正确"}
        else:
            return {"ok": False, "msg": f"HTTP 错误 {resp.status_code}: {resp.text[:100]}"}

    except requests.exceptions.Timeout:
        return {"ok": False, "msg": "连接超时：服务器响应时间过长"}
    except requests.exceptions.ConnectionError:
        return {"ok": False, "msg": "连接失败：无法访问目标地址，请检查网络和 URL"}
    except Exception as e:
        return {"ok": False, "msg": f"连接异常: {str(e)[:80]}"}
