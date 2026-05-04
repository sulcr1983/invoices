import os
import logging
try:
    from .core.baidu_ocr import is_baidu_ocr_available, extract_from_baidu_vat_invoice
    from .core.pdf_utils import extract_from_pdf_plumber
    from .core.text_invoice_parser import parse_invoice_text_fallback
    from .core.invoice_parser import map_baidu_vat_result
    from .core.data_utils import calculate_file_md5
except ImportError:
    from core.baidu_ocr import is_baidu_ocr_available, extract_from_baidu_vat_invoice
    from core.pdf_utils import extract_from_pdf_plumber
    from core.text_invoice_parser import parse_invoice_text_fallback
    from core.invoice_parser import map_baidu_vat_result
    from core.data_utils import calculate_file_md5

logger = logging.getLogger(__name__)


def extract_invoice(file_path):
    if not os.path.exists(file_path):
        logger.error(f"文件不存在: {file_path}")
        return None

    file_md5 = calculate_file_md5(file_path)
    if not file_md5:
        logger.error(f"无法计算文件MD5: {file_path}")
        return None

    ext = os.path.splitext(file_path)[1].lower()
    record = None
    extraction_method = None

    if is_baidu_ocr_available():
        words_result = extract_from_baidu_vat_invoice(file_path)
        if words_result:
            result = map_baidu_vat_result(words_result)
            if isinstance(result, tuple) and len(result) == 2:
                record, details = result
            else:
                record = result
                details = []
            extraction_method = "BaiduVatInvoice"

    if not record:
        logger.info(f"百度OCR未返回可用结果，尝试PDF文本提取: {file_path}")
        if ext == '.pdf':
            text = extract_from_pdf_plumber(file_path)
            if text:
                record = parse_invoice_text_fallback(text, file_path)
                extraction_method = "pdfplumber"
                details = []

    if not record:
        logger.warning(f"无法从文件提取数据: {file_path}")
        return None, []

    record['file_md5'] = file_md5
    logger.info(f"发票提取完成: {record.get('invoice_num')}, 提取方式: {extraction_method}, MD5: {file_md5}")

    if not extraction_method:
        details = []
    return record, details
