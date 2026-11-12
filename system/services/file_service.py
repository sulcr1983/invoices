import shutil
import logging
from pathlib import Path
from datetime import datetime

from ..config import INPUT_DIR, PROCESSING_DIR, ARCHIVE_DIR, FAILED_DIR, DUPLICATE_DIR

logger = logging.getLogger(__name__)


def ensure_directories():
    for dir_path in [INPUT_DIR, PROCESSING_DIR, ARCHIVE_DIR, FAILED_DIR, DUPLICATE_DIR]:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
    logger.info("所有目录检查完成")


_PENDING_EXTS = {'.pdf', '.ofd', '.jpg', '.jpeg', '.png'}


def scan_pending_files():
    """扫描待识别目录，只返回受支持的发票文件。

    之前会把 desktop.ini、.gitkeep、.db 等一并送入流水线，
    白白消耗 OCR 额度并制造"失败文件"。
    """
    try:
        input_path = Path(INPUT_DIR)
        files = []
        skipped = []
        for f in input_path.iterdir():
            if not f.is_file():
                continue
            if f.suffix.lower() in _PENDING_EXTS:
                files.append(f.name)
            else:
                skipped.append(f.name)
        if skipped:
            logger.warning(f"跳过非发票文件 {len(skipped)} 个: {', '.join(skipped[:5])}")
        logger.debug(f"扫描待处理文件: 发现 {len(files)} 个文件")
        return files
    except Exception as e:
        logger.error(f"扫描目录失败: {e}")
        return []


def sanitize_filename(name):
    """文件名清洗：与 clean_seller_name 共用同一套规则，避免两份实现漂移。"""
    from ..core.data_utils import clean_seller_name
    return clean_seller_name(name)


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

    seller_clean = sanitize_filename(seller) if seller else '未知单位'
    amount_str = f"{amount:.2f}" if amount else '0.00'
    base_name = f"{date_str}_{seller_clean}_{amount_str}_{invoice_num}{ext}"

    # 重名一律走 _1/_2 递增，绝不返回已存在的旧路径，
    # 否则新文件会滞留在处理中目录且下次不再被扫描（静默丢件）。
    target_path = archive_subdir / base_name
    counter = 1
    while target_path.exists():
        name_parts = base_name.rsplit('.', 1)
        target_path = archive_subdir / f"{name_parts[0]}_{counter}.{name_parts[1]}"
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

    # 目标已存在时自动改名，绝不静默跳过（否则原件会永久滞留在处理中目录）
    if dest.exists():
        stem, suffix = dest.stem, dest.suffix
        counter = 1
        while dest.exists():
            dest = dest.with_name(f"{stem}_{counter}{suffix}")
            counter += 1
        logger.warning(f"归档目标已存在，改用新路径: {dest}")

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
