import os
import sys
import logging
import uuid
from datetime import datetime

try:
    from ..config import INPUT_DIR, FAILED_DIR, DB_PATH, LEDGER_PATH
except ImportError:
    from config import INPUT_DIR, FAILED_DIR, DB_PATH, LEDGER_PATH

try:
    from ..db_manager import DBManager
except ImportError:
    from db_manager import DBManager

try:
    from ..services.file_service import ensure_directories
except ImportError:
    from services.file_service import ensure_directories

try:
    from ..services import (
        scan_pending_files, move_to_processing, move_from_processing,
        get_archive_path, process_invoice_file, push_invoice, compensate_pending
    )
except ImportError:
    from services import (
        scan_pending_files, move_to_processing, move_from_processing,
        get_archive_path, process_invoice_file, push_invoice, compensate_pending
    )

try:
    from ..extractor import calculate_file_md5
except ImportError:
    from extractor import calculate_file_md5

logger = logging.getLogger(__name__)

PROCESS_INSTANCE_ID = uuid.uuid4().hex[:8]


def generate_batch_id():
    return datetime.now().strftime("%Y%m%d%H%M%S%f")


def relocate_failed_to_input():
    import shutil
    if not os.path.exists(str(FAILED_DIR)):
        return 0

    files = [f for f in os.listdir(str(FAILED_DIR)) if os.path.isfile(os.path.join(str(FAILED_DIR), f))]
    if not files:
        return 0

    count = 0
    for filename in files:
        src_path = os.path.join(str(FAILED_DIR), filename)
        dst_path = os.path.join(str(INPUT_DIR), filename)

        if os.path.exists(dst_path):
            name, ext = os.path.splitext(filename)
            counter = 1
            while os.path.exists(dst_path):
                dst_path = os.path.join(str(INPUT_DIR), f"{name}_{counter}{ext}")
                counter += 1

        try:
            shutil.move(src_path, dst_path)
            logger.info(f"文件从失败目录移回待识别: {filename}")
            count += 1
        except Exception as e:
            logger.warning(f"移动文件失败: {filename}, 错误: {e}")

    if count > 0:
        logger.info(f"已将 {count} 个文件从失败目录移回待识别目录")
    return count


def check_environment():
    logger.info("开始环境自检")
    logger.info(f"Python 路径: {sys.executable}")
    logger.info(f"Python 版本: {sys.version}")

    required_libs = {
        'pdfplumber': 'pdfplumber',
        'requests': 'requests',
        'pandas': 'pandas',
        'PIL': 'pillow',
        'dotenv': 'python-dotenv',
        'Flask': 'flask',
        'sqlite3': 'sqlite3 (内置)',
        'fitz': 'PyMuPDF',
    }

    all_ok = True
    for display_name, import_name in required_libs.items():
        try:
            if display_name == 'sqlite3':
                import sqlite3
                logger.info(f"{display_name}: 已安装")
            elif display_name == 'fitz':
                import fitz
                logger.info(f"{display_name}: {fitz.version}")
            elif import_name == 'pdfplumber':
                import pdfplumber
                logger.info(f"{display_name}: {pdfplumber.__version__}")
            elif import_name == 'pillow':
                from PIL import __version__ as pillow_version
                logger.info(f"{display_name}: {pillow_version}")
            elif import_name == 'python-dotenv':
                import dotenv
                logger.info(f"{display_name}: 已安装")
            else:
                module = __import__(import_name)
                version = getattr(module, '__version__', '未知')
                logger.info(f"{display_name}: {version}")
        except ImportError as e:
            logger.error(f"{display_name}: 未安装 ({e})")
            all_ok = False
        except Exception as e:
            logger.warning(f"{display_name}: 检查失败 ({e})")

    try:
        import sqlite3
        conn = sqlite3.connect(str(DB_PATH), timeout=5)
        cursor = conn.cursor()
        cursor.execute("SELECT sqlite_version()")
        version = cursor.fetchone()[0]
        conn.close()
        logger.info(f"SQLite 连接成功 (版本: {version})")
        logger.info(f"数据库路径: {DB_PATH}")
    except Exception as e:
        logger.error(f"SQLite 连接失败: {e}")
        all_ok = False

    logger.info("环境自检完成")
    return all_ok


def run_pipeline():
    logger.info("=" * 60)
    logger.info("天颐 发票处理系统启动")
    logger.info("=" * 60)

    ensure_directories()

    logger.info("检查失败目录，将文件移回待识别...")
    relocated = relocate_failed_to_input()
    if relocated > 0:
        print(f"[自动归位] 已将 {relocated} 个文件从失败目录移回待识别目录")

    if not check_environment():
        logger.warning("环境检查发现问题，但将继续运行...")
    else:
        print("[环境检查] 一切正常，准备处理发票...")

    db_manager = DBManager(DB_PATH)

    batch_id = generate_batch_id()
    logger.info(f"本次批次ID: {batch_id}")

    logger.info("执行自愈补偿机制...")
    compensate_pending(db_manager)

    logger.info("正在扫描 待识别发票 目录...")
    pending_files = scan_pending_files()

    if not pending_files:
        logger.info("待识别发票 文件夹为空，无需处理")
        return {'success': 0, 'duplicate': 0, 'failed': 0}, batch_id

    logger.info(f"发现 {len(pending_files)} 个文件待处理")
    logger.info("执行文件级重复预检查...")

    files_to_skip = []
    stats = {'success': 0, 'duplicate': 0, 'failed': 0}
    for filename in pending_files:
        file_path = os.path.join(str(INPUT_DIR), filename)
        file_md5 = calculate_file_md5(file_path)
        if file_md5:
            existing = db_manager.get_record_by_md5(file_md5)
            if existing:
                existing_invoice_num = existing[1] if len(existing) > 1 else ''
                existing_seller = existing[2] if len(existing) > 2 else ''
                existing_date = existing[4] if len(existing) > 4 else ''
                existing_amount = existing[11] if len(existing) > 11 else 0
                existing_code = existing[12] if len(existing) > 12 else ''
                logger.warning(f"文件已在数据库中(MD5重复): {filename} -> {existing_invoice_num}")
                db_manager.log_duplicate_record(
                    invoice_num=existing_invoice_num,
                    seller=existing_seller,
                    date=existing_date,
                    total_amount=existing_amount or 0,
                    invoice_code=existing_code,
                    file_md5=file_md5,
                    duplicate_type='duplicate_md5',
                    existing_invoice_num=existing_invoice_num,
                    filename=filename,
                    batch_id=batch_id
                )
                from services.file_service import move_to_duplicate
                try:
                    move_to_duplicate(file_path, filename)
                    logger.info(f"文件移至重复目录: {filename}")
                except Exception as e:
                    logger.error(f"移动重复文件失败: {filename}, 错误: {e}")
                files_to_skip.append(filename)
                stats['duplicate'] += 1

    pending_files = [f for f in pending_files if f not in files_to_skip]
    logger.info(f"预检查后剩余 {len(pending_files)} 个文件待处理")

    if not pending_files:
        return {'success': 0, 'duplicate': len(files_to_skip), 'failed': 0}, batch_id

    for filename in pending_files:
        file_path = os.path.join(str(INPUT_DIR), filename)
        absolute_file_path = os.path.abspath(file_path)

        lock_key = f"process:{absolute_file_path}"
        if not db_manager.acquire_file_lock(lock_key, PROCESS_INSTANCE_ID, timeout=10):
            logger.warning(f"文件已被其他实例锁定，跳过: {filename}")
            continue

        logger.info(f"开始处理: {filename}")

        processing_path = None
        try:
            processing_path = move_to_processing(file_path)
        except Exception as e:
            logger.error(f"文件移入processing失败: {filename}, 错误: {e}")
            db_manager.release_file_lock(lock_key, PROCESS_INSTANCE_ID)
            stats['failed'] += 1
            continue

        try:
            status, result = process_invoice_file(processing_path, db_manager, batch_id=batch_id)

            if status == 'success':
                record = result
                push_ok, push_error = push_invoice(record, db_manager)

                if push_ok:
                    logger.info(f"推送企微成功: {record.get('invoice_num')}")
                else:
                    logger.warning(f"推送企微失败(稍后补偿): {record.get('invoice_num')}, {push_error}")

                ext = os.path.splitext(processing_path)[1]
                archive_path = get_archive_path(
                    record.get('seller', ''),
                    record.get('invoice_num', ''),
                    record.get('total_amount', 0),
                    ext,
                    invoice_date=record.get('date', None)
                )
                try:
                    move_from_processing(processing_path, archive_path)
                    logger.info(f"归档成功: {archive_path}")
                except Exception as e:
                    logger.error(f"归档失败: {processing_path} -> {archive_path}, 错误: {e}")
                    try:
                        from services.file_service import move_to_failed
                        move_to_failed(processing_path, filename)
                    except Exception:
                        pass
                    stats['failed'] += 1
            elif status == 'duplicate':
                logger.info(f"文件重复: {filename}")

            stats[status] = stats.get(status, 0) + 1
        finally:
            db_manager.release_file_lock(lock_key, PROCESS_INSTANCE_ID)

    logger.info("导出账本到 发票台账.csv...")
    csv_path = db_manager.export_to_csv(LEDGER_PATH)
    logger.info(f"账本已导出: {csv_path}")

    logger.info(f"处理汇总: 成功{stats['success']}, 重复{stats['duplicate']}, 失败{stats['failed']}")
    return stats, batch_id


def print_summary_table(stats):
    total = stats['success'] + stats['duplicate'] + stats['failed']

    print("\n" + "=" * 60)
    print("                      处理汇总报告")
    print("=" * 60)
    print(f"  {'项目':<20} {'数量':<10} {'去向':<25}")
    print("-" * 60)
    print(f"  {'本次处理总数':<18} {total:<10} {'-':<25}")
    print(f"  {'[OK] 成功归档':<18} {stats['success']:<10} {'已归档发票':<25}")
    print(f"  {'[FAIL] 识别失败':<18} {stats['failed']:<10} {'识别失败待处理':<25}")
    print(f"  {'[WARN] 重复发票':<18} {stats['duplicate']:<10} {'重复发票记录':<25}")
    print("=" * 60)
    print(f"\n[提示] 若企业微信未收到数据，请检查网络后再次运行脚本，系统将自动补发")
