import shutil
import json
import sys
import logging
import uuid
from pathlib import Path
from datetime import datetime

from ..config import INPUT_DIR, FAILED_DIR, PROCESSING_DIR, DB_PATH, LEDGER_PATH, RETRY_MAX_ATTEMPTS
from ..db_manager import DBManager
from ..services.file_service import ensure_directories
from ..services import (
    scan_pending_files, move_to_processing, move_from_processing,
    get_archive_path, process_invoice_file, push_invoice, compensate_pending
)
from ..extractor import calculate_file_md5
from .risk_checker import run_risk_check

logger = logging.getLogger(__name__)

PROCESS_INSTANCE_ID = uuid.uuid4().hex[:8]


def generate_batch_id():
    """生成一次发票处理批次的唯一编号。"""
    return datetime.now().strftime("%Y%m%d%H%M%S%f")


def _retry_ledger_path():
    return Path(FAILED_DIR) / '.retry_count.json'


def _load_retry_ledger():
    p = _retry_ledger_path()
    try:
        if p.exists():
            return json.loads(p.read_text(encoding='utf-8'))
    except Exception as e:
        logger.warning(f"读取重试计数失败，按空处理: {e}")
    return {}


def _save_retry_ledger(ledger):
    try:
        _retry_ledger_path().write_text(json.dumps(ledger, ensure_ascii=False), encoding='utf-8')
    except Exception as e:
        logger.warning(f"写入重试计数失败: {e}")


def recover_processing_dir():
    """把上次中断遗留在 X-处理中临时 的文件放回待识别目录。

    后台线程是 daemon，关窗/断电会直接被杀，文件会卡在处理中目录且
    下次不会被扫描（只扫待识别目录）——这是静默丢件的根源。
    """
    proc_dir = Path(PROCESSING_DIR)
    if not proc_dir.exists():
        return 0
    count = 0
    for src_path in [f for f in proc_dir.iterdir() if f.is_file()]:
        dst_path = Path(INPUT_DIR) / src_path.name
        counter = 1
        while dst_path.exists():
            dst_path = Path(INPUT_DIR) / f"{src_path.stem}_r{counter}{src_path.suffix}"
            counter += 1
        try:
            shutil.move(str(src_path), str(dst_path))
            logger.warning(f"恢复中断文件到待识别目录: {src_path.name}")
            count += 1
        except Exception as e:
            logger.error(f"恢复中断文件失败: {src_path.name}, 错误: {e}")
    if count:
        logger.warning(f"本次从上一次中断中恢复了 {count} 个文件")
    return count


def relocate_failed_to_input():
    """将失败目录中的文件放回待识别目录，便于重新处理。

    带重试上限：超过 RETRY_MAX_ATTEMPTS 次仍失败的坏文件不再自动回流，
    避免每次启动都重复消耗 OCR 额度。
    """
    failed_dir = Path(FAILED_DIR)
    if not failed_dir.exists():
        return 0

    files = [f for f in failed_dir.iterdir() if f.is_file() and f.name != '.retry_count.json']
    if not files:
        return 0

    ledger = _load_retry_ledger()
    count = 0
    for src_path in files:
        attempts = int(ledger.get(src_path.name, 0))
        if attempts >= RETRY_MAX_ATTEMPTS:
            logger.warning(f"重试已达上限，保留在失败目录: {src_path.name}（{attempts} 次）")
            continue

        dst_path = Path(INPUT_DIR) / src_path.name
        if dst_path.exists():
            counter = 1
            while dst_path.exists():
                dst_path = Path(INPUT_DIR) / f"{src_path.stem}_{counter}{src_path.suffix}"
                counter += 1

        try:
            shutil.move(str(src_path), str(dst_path))
            ledger[src_path.name] = attempts + 1
            logger.info(f"文件从失败目录移回待识别（第 {attempts + 1} 次）: {src_path.name}")
            count += 1
        except Exception as e:
            logger.warning(f"移动文件失败: {src_path.name}, 错误: {e}")

    _save_retry_ledger(ledger)
    if count > 0:
        logger.info(f"已将 {count} 个文件从失败目录移回待识别目录")
    return count


def check_environment():
    """检查依赖库、数据库和目录是否满足本地处理要求。"""
    logger.info("开始环境自检")
    logger.info(f"Python 路径: {sys.executable}")
    logger.info(f"Python 版本: {sys.version}")

    required_libs = {
        'pdfplumber': 'pdfplumber',
        'requests': 'requests',
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
    """执行完整发票处理流程：扫描、识别、入库、归档并推送结果。"""
    logger.info("=" * 60)
    logger.info("SuperSu 发票处理系统启动")
    logger.info("=" * 60)

    ensure_directories()

    # 先恢复上次中断遗留在“处理中”目录的文件，再回流失败文件
    recover_processing_dir()

    logger.info("检查失败目录，将文件移回待识别...")
    relocated = relocate_failed_to_input()
    if relocated > 0:
        logger.info(f"已将 {relocated} 个文件从失败目录移回待识别目录")

    if not check_environment():
        logger.warning("环境检查发现问题，但将继续运行...")
    else:
        logger.info("环境检查通过，准备处理发票")

    db_manager = DBManager(DB_PATH)

    batch_id = generate_batch_id()
    logger.info(f"本次批次ID: {batch_id}")

    logger.info("执行自愈补偿机制...")
    compensate_pending(db_manager)

    logger.info("正在扫描 待识别发票 目录...")
    pending_files = scan_pending_files()

    if not pending_files:
        logger.info("待识别发票 文件夹为空，无需处理")
        return {'success': 0, 'duplicate': 0, 'failed': 0, 'failed_files': []}, batch_id

    logger.info(f"发现 {len(pending_files)} 个文件待处理")
    logger.info("执行文件级重复预检查...")

    files_to_skip = []
    stats = {'success': 0, 'duplicate': 0, 'failed': 0, 'failed_files': []}
    for filename in pending_files:
        file_path = str(Path(INPUT_DIR) / filename)
        file_md5 = calculate_file_md5(file_path)
        if file_md5:
            existing = db_manager.get_record_by_md5(file_md5)
            if existing:
                existing_invoice_num = existing.get('invoice_num', '')
                existing_seller = existing.get('seller', '')
                existing_date = existing.get('date', '')
                existing_amount = existing.get('total_amount', 0)
                existing_code = existing.get('invoice_code', '')
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
                from ..services.file_service import move_to_duplicate
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
        return {'success': 0, 'duplicate': len(files_to_skip), 'failed': 0, 'failed_files': []}, batch_id

    for filename in pending_files:
        file_path = str(Path(INPUT_DIR) / filename)
        absolute_file_path = str(Path(file_path).resolve())

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
            stats['failed_files'].append({'filename': filename, 'reason': f'move_error: {e}'})
            continue

        try:
            status, result = process_invoice_file(processing_path, db_manager, batch_id=batch_id)

            if status == 'success':
                record = result

                # 说明：批量处理不做自动验真（验真按次计费，且需要人工确认）。
                # 验真统一走前端「单张/批量验真」入口，此处保持 unverified。
                record['verify_status'] = 'unverified'

                risk_flags = run_risk_check(record, db_manager)
                if risk_flags:
                    record['risk_flags'] = risk_flags
                    db_manager.update_risk_flags(
                        record.get('invoice_num', ''),
                        risk_flags
                    )

                push_ok, push_error = push_invoice(record, db_manager)

                if push_ok:
                    logger.info(f"推送企微成功: {record.get('invoice_num')}")
                elif push_error == 'skipped':
                    logger.info(f"未配置推送目标，已跳过: {record.get('invoice_num')}")
                else:
                    logger.warning(f"推送企微失败(稍后补偿): {record.get('invoice_num')}, {push_error}")

                ext = Path(processing_path).suffix
                archive_path = get_archive_path(
                    record.get('seller', ''),
                    record.get('invoice_num', ''),
                    record.get('total_amount', 0),
                    ext,
                    invoice_date=record.get('date', None)
                )
                archive_ok = False
                try:
                    actual_path = move_from_processing(processing_path, archive_path)
                    # 校验原件确实已离开处理中目录，避免“假归档成功”
                    if Path(processing_path).exists():
                        raise RuntimeError('文件仍滞留在处理中目录')
                    archive_ok = True
                    logger.info(f"归档成功: {actual_path}")
                except Exception as e:
                    logger.error(f"归档失败: {processing_path} -> {archive_path}, 错误: {e}")
                    try:
                        from ..services.file_service import move_to_failed
                        move_to_failed(processing_path, filename)
                    except Exception as move_err:
                        logger.error(f"归档失败后移入失败目录也失败: {filename}, {move_err}")
                    stats['failed'] += 1
                    stats['failed_files'].append({'filename': filename, 'reason': 'archive_error'})

                if archive_ok:
                    stats['success'] += 1
                # 归档失败已在上面计入 failed，这里不再重复计数
                continue
            elif status == 'duplicate':
                logger.info(f"文件重复: {filename}")
            else:
                error_reason = result or 'unknown_error'
                stats['failed_files'].append({'filename': filename, 'reason': error_reason})

            stats[status] = stats.get(status, 0) + 1
        finally:
            db_manager.release_file_lock(lock_key, PROCESS_INSTANCE_ID)

    logger.info("导出账本到 发票台账.csv...")
    csv_path = db_manager.export_to_csv(LEDGER_PATH)
    logger.info(f"账本已导出: {csv_path}")

    logger.info(f"处理汇总: 成功{stats['success']}, 重复{stats['duplicate']}, 失败{stats['failed']}")
    return stats, batch_id
