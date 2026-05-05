import logging
from pathlib import Path

try:
    from .core.baidu_ocr import is_baidu_ocr_available, extract_from_baidu_vat_invoice
    from .core.pdf_utils import extract_from_pdf_plumber
    from .core.text_invoice_parser import parse_invoice_text_fallback
    from .core.invoice_parser import map_baidu_vat_result
    from .core.ofd_parser import is_ofd_file, extract_invoice_from_ofd
    from .core.data_utils import calculate_file_md5
except ImportError:
    from core.baidu_ocr import is_baidu_ocr_available, extract_from_baidu_vat_invoice
    from core.pdf_utils import extract_from_pdf_plumber
    from core.text_invoice_parser import parse_invoice_text_fallback
    from core.invoice_parser import map_baidu_vat_result
    from core.ofd_parser import is_ofd_file, extract_invoice_from_ofd
    from core.data_utils import calculate_file_md5

logger = logging.getLogger(__name__)


def extract_invoice(file_path):
    fp = Path(file_path)
    if not fp.exists():
        logger.error(f"文件不存在: {file_path}")
        return None

    file_md5 = calculate_file_md5(file_path)
    if not file_md5:
        logger.error(f"无法计算文件MD5: {file_path}")
        return None

    ext = fp.suffix.lower()
    record = None
    extraction_method = None
    details = []

    if ext == '.ofd':
        ofd_result = extract_invoice_from_ofd(file_path)
        if ofd_result:
            if isinstance(ofd_result, tuple) and len(ofd_result) == 2:
                first, second = ofd_result
                if first == 'OCR_NEEDED':
                    logger.info(f"OFD内嵌XML未找到发票数据，尝试OCR识别图片: {file_path}")
                    if is_baidu_ocr_available():
                        words_result = extract_from_baidu_vat_invoice(file_path)
                        if words_result:
                            result = map_baidu_vat_result(words_result)
                            if isinstance(result, tuple) and len(result) == 2:
                                record, details = result
                            else:
                                record = result
                                details = []
                            extraction_method = "BaiduVatInvoice(OFD)"
                elif isinstance(first, dict):
                    record, details = first, second
                    extraction_method = "OFD_XML"
            if not record and not extraction_method:
                record = None
        else:
            logger.warning(f"OFD文件解析无结果: {file_path}")

    if not record and ext != '.ofd':
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

    if not record and ext == '.pdf':
        logger.info(f"百度OCR未返回可用结果，尝试PDF文本提取: {file_path}")
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
