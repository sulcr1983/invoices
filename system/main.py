import logging
import argparse

from .config import (
    DB_PATH, LOG_LEVEL, LOG_FORMAT,
    setup_logging as config_setup_logging
)
from .core.pipeline import check_environment, run_pipeline, generate_batch_id, print_summary_table
from .services.file_service import ensure_directories
from .db_manager import DBManager
from .services import scan_pending_files, compensate_pending

logger = logging.getLogger(__name__)


def cmd_run():
    logger.info("[CLI] 执行 run 命令")
    stats, batch_id = run_pipeline()
    print_summary_table(stats)
    return stats


def cmd_retry():
    logger.info("[CLI] 执行 retry 命令")
    ensure_directories()

    if not check_environment():
        logger.warning("环境检查发现问题，但将继续运行...")
    else:
        print("[环境检查] 一切正常，准备执行补偿...")

    db_manager = DBManager(DB_PATH)
    batch_id = generate_batch_id()
    logger.info(f"补偿批次ID: {batch_id}")
    logger.info("开始执行失败补偿...")
    compensate_pending(db_manager)

    print("\n" + "=" * 60)
    print("                      补偿执行报告")
    print("=" * 60)
    print(f"  批次ID: {batch_id}")
    print(f"  当前失败记录数: {db_manager.get_failed_count()}")
    print(f"  当前未推送记录数: {db_manager.get_unsynced_count()}")
    print("=" * 60)
    return db_manager.get_failed_count()


def cmd_check():
    logger.info("[CLI] 执行 check 命令")
    ensure_directories()

    if not check_environment():
        logger.warning("环境检查发现问题，但将继续运行...")
    else:
        print("[环境检查] 一切正常，系统状态如下...")

    db_manager = DBManager(DB_PATH)
    pending_files = scan_pending_files()
    failed_count = db_manager.get_failed_count()
    unsynced_count = db_manager.get_unsynced_count()

    print("\n" + "=" * 60)
    print("                      系统状态检查")
    print("=" * 60)
    print(f"  待处理文件数: {len(pending_files)}")
    print(f"  失败记录数:   {failed_count}")
    print(f"  未推送记录数: {unsynced_count}")
    print("=" * 60)
    return {'pending_files': len(pending_files), 'failed_count': failed_count, 'unsynced_count': unsynced_count}


def main():
    ensure_directories()

    parser = argparse.ArgumentParser(
        description='天颐 发票处理系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
可用命令:
  python main.py run    执行完整处理流程
  python main.py retry  执行失败补偿
  python main.py check  输出系统状态

示例:
  python main.py run    # 扫描并处理发票
  python main.py retry  # 重试失败的推送
  python main.py check  # 查看待处理/失败/未推送数量
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    parser_run = subparsers.add_parser('run', help='执行完整处理流程')
    parser_run.add_argument('--no-input', action='store_true', help='跳过按回车退出')
    parser_retry = subparsers.add_parser('retry', help='执行失败补偿')
    parser_retry.add_argument('--no-input', action='store_true', help='跳过按回车退出')
    parser_check = subparsers.add_parser('check', help='输出系统状态')
    parser_check.add_argument('--no-input', action='store_true', help='跳过按回车退出')

    args = parser.parse_args()

    if not args.command:
        print("[提示] 未指定命令，默认执行 'run' 完整流程")
        args.command = 'run'
        args.no_input = False

    config_setup_logging()

    if args.command == 'run':
        cmd_run()
        if not args.no_input:
            input("\n处理完毕，按回车键退出...")
    elif args.command == 'retry':
        cmd_retry()
        if not args.no_input:
            input("\n补偿完毕，按回车键退出...")
    elif args.command == 'check':
        cmd_check()
        if not args.no_input:
            input("\n检查完毕，按回车键退出...")


if __name__ == "__main__":
    main()
