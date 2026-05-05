import logging
from pathlib import Path

from ..extractor import extract_invoice
from ..core.data_utils import calculate_file_md5
from ..core.text_invoice_parser import validate_invoice as extractor_validate

logger = logging.getLogger(__name__)


def validate_invoice_record(record):
    return extractor_validate(record)


def extract_invoice_data(file_path):
    try:
        file_md5 = calculate_file_md5(file_path)
        if not file_md5:
            logger.error(f"无法计算MD5: {file_path}")
            return None, None, "md5_error"

        result = extract_invoice(file_path)
        if not result:
            logger.warning(f"发票识别失败: {file_path}")
            return None, None, "extract_error"

        if isinstance(result, tuple) and len(result) == 2:
            record, details = result
        else:
            record = result
            details = []

        if not record:
            logger.warning(f"发票解析结果为空: {file_path}")
            return None, None, "extract_error"

        record['file_md5'] = file_md5

        is_valid, errors = validate_invoice_record(record)
        if not is_valid:
            error_msg = "; ".join(errors)
            logger.warning(f"数据校验失败: {error_msg}")
            return None, None, f"validation_error: {error_msg}"

        return record, details, None

    except Exception as e:
        logger.error(f"发票处理异常: {file_path}, 错误: {e}")
        return None, None, f"exception: {e}"


def process_invoice_file(processing_path, db_manager, batch_id=None):
    from .file_service import move_to_failed, move_to_duplicate

    original_filename = Path(processing_path).name

    try:
        record, details, error = extract_invoice_data(processing_path)

        if error:
            try:
                move_to_failed(processing_path, original_filename)
            except Exception as move_err:
                logger.error(f"移动文件到失败目录失败: {original_filename}, 错误: {move_err}")
            return 'failed', error

        success, reason, record_with_error = db_manager.insert_record_with_transaction(record, batch_id=batch_id)

        if not success:
            if reason in ('duplicate_invoice_num', 'duplicate_md5'):
                logger.warning(f"发票重复: {record.get('invoice_num')}, reason={reason}")
                db_manager.log_duplicate_record(
                    invoice_num=record.get('invoice_num', ''),
                    seller=record.get('seller', ''),
                    date=record.get('date', ''),
                    total_amount=record.get('total_amount', 0),
                    invoice_code=record.get('invoice_code', ''),
                    file_md5=record.get('file_md5', ''),
                    duplicate_type=reason,
                    existing_invoice_num=record.get('invoice_num', ''),
                    filename=original_filename,
                    batch_id=batch_id or ''
                )
                try:
                    move_to_duplicate(processing_path, original_filename)
                except Exception as move_err:
                    logger.error(f"移动文件到重复目录失败: {original_filename}, 错误: {move_err}")
                return 'duplicate', reason
            else:
                logger.error(f"数据库插入失败，流程停止: {reason}")
                try:
                    db_manager.update_error_type(
                        record.get('invoice_num', 'unknown'),
                        reason,
                        f"db_insert_error: {reason}"
                    )
                    move_to_failed(processing_path, original_filename)
                except Exception as move_err:
                    logger.error(f"更新错误类型或移动文件失败: {original_filename}, 错误: {move_err}")
                return 'failed', reason

        invoice_num = record.get('invoice_num', '')
        logger.info(f"记录写入数据库成功: {invoice_num}")

        if details:
            invoice_id = db_manager.get_invoice_id_by_num(invoice_num)
            if invoice_id:
                db_manager.insert_invoice_details(invoice_id, details)
                db_manager.verify_invoice_math(invoice_id)
                logger.info(f"明细数据已存储并校验: {invoice_num}")

        return 'success', record

    except Exception as e:
        logger.error(f"处理文件异常: {original_filename}, 错误: {e}")
        try:
            if 'invoice_num' in locals() and record.get('invoice_num'):
                db_manager.update_error_type(
                    record.get('invoice_num', 'unknown'),
                    f'exception: {type(e).__name__}',
                    str(e)
                )
            move_to_failed(processing_path, original_filename)
        except Exception as move_error:
            logger.error(f"移动文件到失败目录失败: {original_filename}, 错误: {move_error}")
        return 'failed', str(e)
