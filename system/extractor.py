import logging
from pathlib import Path

from .core.baidu_ocr import is_baidu_ocr_available, extract_from_baidu_vat_invoice
from .core.pdf_utils import extract_from_pdf_plumber
from .core.text_invoice_parser import parse_invoice_text_fallback
from .core.invoice_parser import map_baidu_vat_result
from .core.ofd_parser import is_ofd_file, extract_invoice_from_ofd
from .core.data_utils import calculate_file_md5

logger = logging.getLogger(__name__)


def _try_easyofd_text(file_path):
    """用 easyofd 把 OFD 转成 PDF，再复用既有文本/OCR 通道取文字。

    说明：本机当前没有真实 OFD 样本，此路径按 easyofd 公开接口实现，
    任何异常都会被吞掉并回落到手写解析器，不影响原有行为。
    """
    try:
        from easyofd import OFD
    except ImportError:
        return None

    import os
    import tempfile

    tmp_path = None
    try:
        ofd = OFD()
        ofd.read(file_path)
        pdf_bytes = ofd.to_pdf()
        if not pdf_bytes:
            return None
        fd, tmp_path = tempfile.mkstemp(suffix='.pdf')
        with os.fdopen(fd, 'wb') as fh:
            fh.write(pdf_bytes)

        text = extract_from_pdf_plumber(tmp_path)
        if text:
            logger.info(f"easyofd 转换后文本提取成功: {file_path}")
            return text

        from .core import local_ocr
        if local_ocr.is_available():
            text = local_ocr.recognize_pdf(tmp_path)
            if text:
                logger.info(f"easyofd 转换后本地 OCR 成功: {file_path}")
                return text
    except Exception as e:
        logger.warning(f"easyofd 兜底失败，忽略: {e}")
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    return None


def extract_invoice(file_path, file_md5=None):
    fp = Path(file_path)
    if not fp.exists():
        logger.error(f"文件不存在: {file_path}")
        return None

    # 允许调用方传入已算好的 MD5，避免大文件重复读取
    if not file_md5:
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

        # 兜底：用手写 XML 解析失败时，交给 easyofd 转 PDF 再走文本/OCR 流程
        if not record:
            text = _try_easyofd_text(file_path)
            if text:
                record = parse_invoice_text_fallback(text, file_path)
                extraction_method = "easyofd"
                details = []

    if not record:
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
        logger.info(f"云端OCR未返回可用结果，尝试PDF文本提取: {file_path}")
        text = extract_from_pdf_plumber(file_path)
        if text:
            record = parse_invoice_text_fallback(text, file_path)
            extraction_method = "pdfplumber"
            details = []

    # 最后一层兜底：本地 OCR（离线、不花钱），覆盖扫描件/图片/无文本层PDF
    if not record:
        try:
            from .core import local_ocr
            if local_ocr.is_available():
                logger.info(f"尝试本地 OCR 兜底: {file_path}")
                text = local_ocr.recognize(file_path)
                if text:
                    record = parse_invoice_text_fallback(text, file_path)
                    extraction_method = "local_rapidocr"
                    details = []
        except Exception as e:
            logger.warning(f"本地 OCR 兜底异常，忽略: {e}")

    if not record:
        logger.warning(f"无法从文件提取数据: {file_path}")
        return None, []

    record['file_md5'] = file_md5
    logger.info(f"发票提取完成: {record.get('invoice_num')}, 提取方式: {extraction_method}, MD5: {file_md5}")

    if not extraction_method:
        details = []
    return record, details
