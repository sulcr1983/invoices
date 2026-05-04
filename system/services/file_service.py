import os
import shutil
import logging
from datetime import datetime

try:
    from ..config import INPUT_DIR, PROCESSING_DIR, ARCHIVE_DIR, FAILED_DIR, DUPLICATE_DIR
except ImportError:
    from config import INPUT_DIR, PROCESSING_DIR, ARCHIVE_DIR, FAILED_DIR, DUPLICATE_DIR

logger = logging.getLogger(__name__)


def ensure_directories():
    for dir_path in [INPUT_DIR, PROCESSING_DIR, ARCHIVE_DIR, FAILED_DIR, DUPLICATE_DIR]:
        os.makedirs(str(dir_path), exist_ok=True)
    logger.info("所有目录检查完成")


def scan_pending_files():
    try:
        files = [f for f in os.listdir(str(INPUT_DIR))
                 if os.path.isfile(os.path.join(str(INPUT_DIR), f))]
        logger.debug(f"扫描待处理文件: 发现 {len(files)} 个文件")
        return files
    except Exception as e:
        logger.error(f"扫描目录失败: {e}")
        return []


def sanitize_filename(name):
    invalid_chars = '\\/:*?"<>|'
    for char in invalid_chars:
        name = name.replace(char, '_')
    return name.strip('_')


def get_archive_path(seller, invoice_num, amount, ext, invoice_date=None):
    if invoice_date:
        try:
            invoice_date_obj = datetime.strptime(invoice_date, '%Y-%m-%d')
            year = invoice_date_obj.strftime('%Y')
            month = invoice_date_obj.strftime('%m')
            date_str = invoice_date_obj.strftime('%Y%m%d')
        except ValueError:
            now = datetime.now()
            year = now.strftime('%Y')
            month = now.strftime('%m')
            date_str = now.strftime('%Y%m%d')
    else:
        now = datetime.now()
        year = now.strftime('%Y')
        month = now.strftime('%m')
        date_str = now.strftime('%Y%m%d')

    archive_subdir = os.path.join(str(ARCHIVE_DIR), year, month)
    os.makedirs(archive_subdir, exist_ok=True)

    existing_files = []
    if os.path.exists(archive_subdir):
        for filename in os.listdir(archive_subdir):
            name_part, ext_part = os.path.splitext(filename)
            if name_part.endswith(f"_{invoice_num}"):
                existing_files.append(filename)

    if existing_files:
        existing_path = os.path.join(archive_subdir, existing_files[0])
        logger.info(f"发票已存在归档: {existing_path}")
        return existing_path

    seller_clean = sanitize_filename(seller) if seller else '未知单位'
    amount_str = f"{amount:.2f}" if amount else '0.00'
    base_name = f"{date_str}_{seller_clean}_{amount_str}_{invoice_num}{ext}"

    target_path = os.path.join(archive_subdir, base_name)
    counter = 1
    while os.path.exists(target_path):
        name_parts = base_name.rsplit('.', 1)
        base_name = f"{name_parts[0]}_{counter}.{name_parts[1]}"
        target_path = os.path.join(archive_subdir, base_name)
        counter += 1

    return target_path


def move_to_processing(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"源文件不存在: {file_path}")

    filename = os.path.basename(file_path)
    processing_path = os.path.join(str(PROCESSING_DIR), filename)

    if os.path.exists(processing_path):
        base, ext = os.path.splitext(filename)
        counter = 1
        while os.path.exists(processing_path):
            processing_path = os.path.join(str(PROCESSING_DIR), f"{base}_{counter}{ext}")
            counter += 1

    try:
        shutil.move(file_path, processing_path)
        logger.debug(f"文件移入processing: {file_path} -> {processing_path}")
        return processing_path
    except Exception as e:
        logger.error(f"文件移入processing失败: {file_path} -> {processing_path}, 错误: {e}")
        raise


def move_from_processing(src_path, dest_path):
    if not os.path.exists(src_path):
        raise FileNotFoundError(f"源文件不存在: {src_path}")

    if os.path.exists(dest_path):
        logger.info(f"目标文件已存在，跳过移动: {dest_path}")
        return dest_path

    dest_dir = os.path.dirname(dest_path)
    if dest_dir and not os.path.exists(dest_dir):
        os.makedirs(dest_dir, exist_ok=True)

    try:
        shutil.move(src_path, dest_path)
        logger.debug(f"文件移动: {src_path} -> {dest_path}")
        return dest_path
    except Exception as e:
        logger.error(f"文件移动失败: {src_path} -> {dest_path}, 错误: {e}")
        raise


def move_to_done(processing_path, dest_path):
    try:
        final_path = move_from_processing(processing_path, dest_path)
        logger.info(f"文件归档成功: {final_path}")
        return final_path
    except Exception as e:
        logger.error(f"文件归档失败: {processing_path} -> {dest_path}, 错误: {e}")
        raise


def move_to_failed(processing_path, original_filename=None):
    if not os.path.exists(processing_path):
        raise FileNotFoundError(f"源文件不存在: {processing_path}")

    filename = original_filename or os.path.basename(processing_path)
    failed_path = os.path.join(str(FAILED_DIR), filename)

    if os.path.exists(failed_path):
        base, ext = os.path.splitext(filename)
        counter = 1
        while os.path.exists(failed_path):
            failed_path = os.path.join(str(FAILED_DIR), f"{base}_{counter}{ext}")
            counter += 1

    try:
        shutil.move(processing_path, failed_path)
        logger.warning(f"文件移至失败目录: {failed_path}")
        return failed_path
    except Exception as e:
        logger.error(f"文件移至失败目录失败: {processing_path} -> {failed_path}, 错误: {e}")
        raise


def move_to_duplicate(processing_path, original_filename=None):
    if not os.path.exists(processing_path):
        raise FileNotFoundError(f"源文件不存在: {processing_path}")

    filename = original_filename or os.path.basename(processing_path)
    duplicate_path = os.path.join(str(DUPLICATE_DIR), filename)

    if os.path.exists(duplicate_path):
        base, ext = os.path.splitext(filename)
        counter = 1
        while os.path.exists(duplicate_path):
            duplicate_path = os.path.join(str(DUPLICATE_DIR), f"{base}_{counter}{ext}")
            counter += 1

    try:
        shutil.move(processing_path, duplicate_path)
        logger.info(f"文件移至重复目录: {duplicate_path}")
        return duplicate_path
    except Exception as e:
        logger.error(f"文件移至重复目录失败: {processing_path} -> {duplicate_path}, 错误: {e}")
        raise
