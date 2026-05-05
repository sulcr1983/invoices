import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

load_dotenv(PROJECT_ROOT / ".env")

INPUT_DIR = PROJECT_ROOT / "待识别发票"
PROCESSING_DIR = PROJECT_ROOT / "X-处理中临时"
ARCHIVE_DIR = PROJECT_ROOT / "已归档发票"
FAILED_DIR = PROJECT_ROOT / "识别失败待处理"
DUPLICATE_DIR = PROJECT_ROOT / "重复发票记录"
DATA_DIR = BASE_DIR / "data"

DB_PATH = DATA_DIR / "invoices.db"
LEDGER_PATH = PROJECT_ROOT / "发票台账.csv"
LOG_PATH = BASE_DIR / "logs" / "app.log"

WECOM_WEBHOOK_URL = __import__('os').environ.get("WECOM_WEBHOOK_URL", "")
WECOM_SCHEMA = __import__('os').environ.get("WECOM_SCHEMA", "{}")

ENABLE_ALERT = __import__('os').environ.get("ENABLE_ALERT", "false").lower() == "true"
ALERT_WEBHOOK_URL = __import__('os').environ.get("ALERT_WEBHOOK_URL", "")

BAIDU_APP_ID = __import__('os').environ.get("BAIDU_APP_ID", "")
BAIDU_API_KEY = __import__('os').environ.get("BAIDU_API_KEY", "")
BAIDU_SECRET_KEY = __import__('os').environ.get("BAIDU_SECRET_KEY", "")
BAIDU_OCR_TYPE = __import__('os').environ.get("BAIDU_OCR_TYPE", "vat_invoice")

INVOICE_FIELD_NAMES = {
    "invoice_num": "发票号码",
    "seller": "销售方名称",
    "seller_tax_id": "销售方纳税识别号",
    "date": "开票日期",
    "buyer": "购买方名称",
    "buyer_tax_id": "购买方纳税识别号",
    "item": "项目/服务内容",
    "price_without_tax": "不含税金额",
    "tax_rate": "税率",
    "tax_amount": "税额",
    "total_amount": "价税合计金额",
    "invoice_code": "发票代码",
    "check_code": "校验码",
    "invoice_type": "发票类型",
    "remark": "备注",
    "file_md5": "文件指纹(MD5)",
    "sync_status": "同步状态",
    "process_time": "处理时间",
    "batch_id": "批次ID",
    "push_status": "推送状态",
    "retry_count": "重试次数",
    "last_error": "最后错误"
}

INVOICE_TEMPLATE = {
    "invoice_code": "",
    "invoice_num": "",
    "date": "",
    "seller": "",
    "seller_tax_id": "",
    "buyer": "",
    "buyer_tax_id": "",
    "item": "",
    "price_without_tax": 0.00,
    "tax_rate": "",
    "tax_amount": 0.00,
    "total_amount": 0.00,
    "check_code": "",
    "invoice_type": "",
    "remark": "",
    "file_md5": "",
    "sync_status": 0,
    "process_time": "",
    "batch_id": ""
}

RETRY_MAX_ATTEMPTS = int(__import__('os').environ.get("RETRY_MAX_ATTEMPTS", "3"))
RETRY_DELAY_SECONDS = int(__import__('os').environ.get("RETRY_DELAY_SECONDS", "2"))
SQLITE_TIMEOUT = int(__import__('os').environ.get("SQLITE_TIMEOUT", "20"))
REQUEST_TIMEOUT = int(__import__('os').environ.get("REQUEST_TIMEOUT", "10"))

LOG_LEVEL = getattr(logging, __import__('os').environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
LOG_FORMAT = "%(asctime)s / %(levelname)s / %(name)s / %(message)s"
LOG_MAX_BYTES = int(__import__('os').environ.get("LOG_MAX_BYTES", 10 * 1024 * 1024))
LOG_BACKUP_COUNT = int(__import__('os').environ.get("LOG_BACKUP_COUNT", "3"))

FILE_ENCODING = "utf-8"
CSV_ENCODING = "utf-8-sig"


def err_to_cn(error_keyword):
    mapping = {
        "ConnectionError": "网络连接失败，请检查网络后重试",
        "webhook": "企业微信推送失败，请检查网络和Webhook配置",
        "Timeout": "请求超时，请检查网络后重试",
        "token": "百度OCR认证失败，请检查 .env 中的 API Key 配置",
        "api_key": "百度OCR配置不完整，请在 .env 中配置 BAIDU_API_KEY 和 BAIDU_SECRET_KEY",
        "OCR": "发票识别服务暂时不可用，请稍后重试",
        "md5": "文件读取失败，请检查文件是否损坏",
        "pdf": "PDF文件解析失败，请确认文件格式正确",
        "database": "数据库操作异常，请联系技术支持",
        "duplicate": "该发票已存在，无需重复导入",
        "validation": "发票数据校验失败，请检查文件内容",
        "validate": "发票数据校验失败，请检查文件内容",
        "exception": "系统发生未知错误，请稍后重试",
    }
    for key, msg in mapping.items():
        if key.lower() in str(error_keyword).lower():
            return msg
    return f"系统处理异常，请稍后重试（错误码：{str(error_keyword)[:50]}）"


def setup_logging():
    log_dir = LOG_PATH.parent
    log_dir.mkdir(parents=True, exist_ok=True)

    rotating_handler = RotatingFileHandler(
        str(LOG_PATH),
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding=FILE_ENCODING
    )
    rotating_handler.setLevel(LOG_LEVEL)
    rotating_handler.setFormatter(logging.Formatter(LOG_FORMAT))

    console_handler = logging.StreamHandler()
    console_handler.setLevel(LOG_LEVEL)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT))

    logging.basicConfig(
        level=LOG_LEVEL,
        handlers=[rotating_handler, console_handler]
    )
    return logging.getLogger(__name__)
