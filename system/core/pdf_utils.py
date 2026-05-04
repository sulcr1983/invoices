import logging

logger = logging.getLogger(__name__)


def pdf_to_images_via_pymupdf(pdf_path):
    try:
        import fitz
        images = []
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            page = doc[page_num]
            mat = fitz.Matrix(300 / 72, 300 / 72)
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("png")
            images.append(img_bytes)
            logger.debug(f"PyMuPDF渲染第{page_num + 1}页成功: {pdf_path}")
        doc.close()
        return images
    except Exception as e:
        logger.error(f"PyMuPDF渲染失败: {pdf_path}, 错误: {e}")
        return None


def extract_from_pdf_plumber(pdf_path):
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            text = ""
            for page in pdf.pages:
                try:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                except Exception as e:
                    logger.warning(f"PDF页面提取异常: {e}")
                    continue
        if not text:
            logger.warning(f"pdfplumber未提取到文本: {pdf_path}")
            return None
        logger.debug(f"pdfplumber提取成功: {pdf_path}, 长度={len(text)}")
        return text
    except Exception as e:
        logger.error(f"pdfplumber提取失败: {pdf_path}, 错误: {e}")
        return None
