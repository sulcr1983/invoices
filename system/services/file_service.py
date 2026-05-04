import shutil
import logging
from pathlib import Path
from datetime import datetime

try:
    from ..config import INPUT_DIR, PROCESSING_DIR, ARCHIVE_DIR, FAILED_DIR, DUPLICATE_DIR
except ImportError:
    from config import INPUT_DIR, PROCESSING_DIR, ARCHIVE_DIR, FAILED_DIR, DUPLICATE_DIR

logger = logging.getLogger(__name__)


def ensure_directories():
    for dir_path in [INPUT_DIR, PROCESSING_DIR, ARCHIVE_DIR, FAILED_DIR, DUPLICATE_DIR]:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
    logger.info("所有目录检查完成")


def scan_pending_files():
    try:
        input_path = Path(INPUT_DIR)
        files = [f.name for f in input_path.iterdir() if f.is_file()]
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

    archive_subdir = Path(ARCHIVE_DIR) / year / month
    archive_subdir.mkdir(parents=True, exist_ok=True)

    existing_files = []
    if archive_subdir.exists():
        for fp in archive_subdir.iterdir():
            if fp.is_file() and fp.stem.endswith(f"_{invoice_num}"):
                existing_files.append(fp.name)

    if existing_files:
        existing_path = str(archive_subdir / existing_files[0])
        logger.info(f"发票已存在归档: {existing_path}")
        return existing_path

    seller_clean = sanitize_filename(seller) if seller else '未知单位'
    amount_str = f"{amount:.2f}" if amount else '0.00'
    base_name = f"{date_str}_{seller_clean}_{amount_str}_{invoice_num}{ext}"

    target_path = archive_subdir / base_name
    counter = 1
    while target_path.exists():
        name_parts = base_name.rsplit('.', 1)
        base_name = f"{name_parts[0]}_{counter}.{name_parts[1]}"
        target_path = archive_subdir / base_name
        counter += 1

    return str(target_path)


def move_to_processing(file_path):
    src = Path(file_path)
    if not src.exists():
        raise FileNotFoundError(f"源文件不存在: {file_path}")

    filename = src.name
    processing_path = Path(PROCESSING_DIR) / filename

    if processing_path.exists():
        base = src.stem
        ext = src.suffix
        counter = 1
        while processing_path.exists():
            processing_path = Path(PROCESSING_DIR) / f"{base}_{counter}{ext}"
            counter += 1

    try:
        shutil.move(str(src), str(processing_path))
        logger.debug(f"文件移入processing: {file_path} -> {processing_path}")
        return str(processing_path)
    except Exception as e:
        logger.error(f"文件移入processing失败: {file_path} -> {processing_path}, 错误: {e}")
        raise


def move_from_processing(src_path, dest_path):
    src = Path(src_path)
    dest = Path(dest_path)
    if not src.exists():
        raise FileNotFoundError(f"源文件不存在: {src_path}")

    if dest.exists():
        logger.info(f"目标文件已存在，跳过移动: {dest_path}")
        return str(dest)

    dest_dir = dest.parent
    if not dest_dir.exists():
        dest_dir.mkdir(parents=True, exist_ok=True)

    try:
        shutil.move(str(src), str(dest))
        logger.debug(f"文件移动: {src_path} -> {dest_path}")
        return str(dest)
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
    src = Path(processing_path)
    if not src.exists():
        raise FileNotFoundError(f"源文件不存在: {processing_path}")

    filename = original_filename or src.name
    failed_path = Path(FAILED_DIR) / filename

    if failed_path.exists():
        stem = Path(filename).stem
        ext = Path(filename).suffix
        counter = 1
        while failed_path.exists():
            failed_path = Path(FAILED_DIR) / f"{stem}_{counter}{ext}"
            counter += 1

    try:
        shutil.move(str(src), str(failed_path))
        logger.warning(f"文件移至失败目录: {failed_path}")
        return str(failed_path)
    except Exception as e:
        logger.error(f"文件移至失败目录失败: {processing_path} -> {failed_path}, 错误: {e}")
        raise


def move_to_duplicate(processing_path, original_filename=None):
    src = Path(processing_path)
    if not src.exists():
        raise FileNotFoundError(f"源文件不存在: {processing_path}")

    filename = original_filename or src.name
    duplicate_path = Path(DUPLICATE_DIR) / filename

    if duplicate_path.exists():
        stem = Path(filename).stem
        ext = Path(filename).suffix
        counter = 1
        while duplicate_path.exists():
            duplicate_path = Path(DUPLICATE_DIR) / f"{stem}_{counter}{ext}"
            counter += 1

    try:
        shutil.move(str(src), str(duplicate_path))
        logger.info(f"文件移至重复目录: {duplicate_path}")
        return str(duplicate_path)
    except Exception as e:
        logger.error(f"文件移至重复目录失败: {processing_path} -> {duplicate_path}, 错误: {e}")
        raise
