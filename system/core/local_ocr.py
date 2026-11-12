# -*- coding: utf-8 -*-
"""本地 OCR（RapidOCR / ONNXRuntime）——离线兜底识别。

定位：当没有配置百度 OCR（或云端调用失败）时，用本地模型把图片/扫描件
转成文本，再交给 text_invoice_parser 做字段抽取。全程不出本机。

设计要点：
- 模型随 rapidocr-onnxruntime 包一起分发，无需联网下载；
- 引擎懒加载（首次调用才初始化，避免拖慢启动）；
- 依赖缺失时静默降级（is_available() 返回 False），不影响主流程。
"""

import logging
import threading

logger = logging.getLogger(__name__)

_engine = None
_engine_lock = threading.Lock()
_init_failed = False

MAX_PDF_PAGES = 2  # 发票通常 1 页，最多渲染 2 页，避免大文件耗时


def is_available():
    """依赖是否可用（不真正初始化引擎）。"""
    try:
        import rapidocr_onnxruntime  # noqa: F401
        return True
    except ImportError:
        return False


def _get_engine():
    global _engine, _init_failed
    if _engine is not None:
        return _engine
    if _init_failed:
        return None
    with _engine_lock:
        if _engine is not None:
            return _engine
        try:
            from rapidocr_onnxruntime import RapidOCR
            _engine = RapidOCR()
            logger.info("本地 OCR 引擎已初始化（RapidOCR）")
        except Exception as e:
            _init_failed = True
            logger.error(f"本地 OCR 初始化失败: {e}")
            return None
    return _engine


def _ocr_image_array(img_array):
    engine = _get_engine()
    if engine is None:
        return None
    try:
        result, _ = engine(img_array)
    except Exception as e:
        logger.error(f"本地 OCR 识别失败: {e}")
        return None
    if not result:
        return None
    # result: [[box, text, score], ...]
    lines = [item[1] for item in result if len(item) >= 2 and item[1]]
    return "\n".join(lines) if lines else None


def recognize_image(file_path):
    """识别单张图片，返回按行拼接的文本。"""
    try:
        import numpy as np
        from PIL import Image
    except ImportError:
        logger.warning("缺少 numpy/Pillow，跳过本地 OCR")
        return None
    try:
        with Image.open(file_path) as im:
            arr = np.array(im.convert('RGB'))
    except Exception as e:
        logger.error(f"读取图片失败: {file_path}, {e}")
        return None
    return _ocr_image_array(arr)


def recognize_pdf(file_path, max_pages=MAX_PDF_PAGES):
    """把 PDF 前几页渲染成图片后识别，返回文本。"""
    try:
        import fitz  # PyMuPDF
        import numpy as np
        from PIL import Image
        import io
    except ImportError:
        logger.warning("缺少 PyMuPDF，跳过 PDF 本地 OCR")
        return None

    texts = []
    try:
        doc = fitz.open(file_path)
        for page_index in range(min(max_pages, doc.page_count)):
            page = doc.load_page(page_index)
            pix = page.get_pixmap(dpi=200)
            img = Image.open(io.BytesIO(pix.tobytes('png'))).convert('RGB')
            text = _ocr_image_array(np.array(img))
            if text:
                texts.append(text)
        doc.close()
    except Exception as e:
        logger.error(f"PDF 本地 OCR 失败: {file_path}, {e}")
        return None
    return "\n".join(texts) if texts else None


def recognize(file_path):
    """按扩展名分派：图片走 recognize_image，PDF 走 recognize_pdf。"""
    from pathlib import Path
    ext = Path(file_path).suffix.lower()
    if ext == '.pdf':
        return recognize_pdf(file_path)
    if ext in ('.jpg', '.jpeg', '.png', '.bmp'):
        return recognize_image(file_path)
    return None
