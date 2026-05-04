import base64
import logging
import time
import requests

import sys
from pathlib import Path

_THIS_DIR = str(Path(__file__).resolve().parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)
_PARENT_DIR = str(Path(__file__).resolve().parent.parent)
if _PARENT_DIR not in sys.path:
    sys.path.insert(0, _PARENT_DIR)

try:
    from ..config import err_to_cn
except ImportError:
    from config import err_to_cn

try:
    from .pdf_utils import pdf_to_images_via_pymupdf
except ImportError:
    from core.pdf_utils import pdf_to_images_via_pymupdf

logger = logging.getLogger(__name__)

_baidu_access_token = None
_baidu_token_expires_time = 0


def get_baidu_access_token():
    global _baidu_access_token, _baidu_token_expires_time

    if _baidu_access_token and time.time() < _baidu_token_expires_time:
        return _baidu_access_token

    try:
        from ..config import BAIDU_API_KEY, BAIDU_SECRET_KEY
        if not BAIDU_API_KEY or not BAIDU_SECRET_KEY:
            logger.warning("百度OCR配置不完整，API Key或Secret Key缺失")
            return None
    except (ImportError, AttributeError):
        try:
            from config import BAIDU_API_KEY, BAIDU_SECRET_KEY
            if not BAIDU_API_KEY or not BAIDU_SECRET_KEY:
                logger.warning("百度OCR配置不完整，API Key或Secret Key缺失")
                return None
        except (ImportError, AttributeError):
            logger.warning("无法读取百度OCR配置")
            return None

    try:
        token_url = "https://aip.baidubce.com/oauth/2.0/token"
        params = {
            "grant_type": "client_credentials",
            "client_id": BAIDU_API_KEY,
            "client_secret": BAIDU_SECRET_KEY
        }
        response = requests.post(token_url, params=params, timeout=10)
        result = response.json()

        if 'access_token' in result:
            _baidu_access_token = result['access_token']
            expires_in = result.get('expires_in', 2592000)
            _baidu_token_expires_time = time.time() + expires_in - 300
            logger.info("百度OCR Access Token 获取成功")
            return _baidu_access_token
        else:
            logger.error(f"百度OCR Token获取失败: {result}")
            return None
    except Exception as e:
        logger.error(f"百度OCR Access Token 请求异常: {e}")
        return None


def is_baidu_ocr_available():
    try:
        from ..config import BAIDU_API_KEY, BAIDU_SECRET_KEY
        return bool(BAIDU_API_KEY and BAIDU_SECRET_KEY)
    except (ImportError, AttributeError):
        try:
            from config import BAIDU_API_KEY, BAIDU_SECRET_KEY
            return bool(BAIDU_API_KEY and BAIDU_SECRET_KEY)
        except (ImportError, AttributeError):
            return False


def extract_from_baidu_vat_invoice(file_path):
    access_token = get_baidu_access_token()
    if not access_token:
        logger.error("无法获取百度OCR Access Token")
        return None

    try:
        ext = file_path.lower()
        if ext.endswith('.pdf'):
            images = pdf_to_images_via_pymupdf(file_path)
            if not images:
                logger.warning(f"PDF转图片失败: {file_path}")
                return None

            for page_num, img_bytes in enumerate(images, 1):
                try:
                    image_base64 = base64.b64encode(img_bytes).decode('utf-8')
                    logger.debug(f"PDF第{page_num}页转Base64成功，长度: {len(image_base64)}")

                    url = f"https://aip.baidubce.com/rest/2.0/ocr/v1/vat_invoice?access_token={access_token}"
                    headers = {"Content-Type": "application/x-www-form-urlencoded"}
                    payload = {"image": image_base64}

                    logger.info(f"正在调用百度OCR API处理第{page_num}页...")
                    response = requests.post(url, data=payload, headers=headers, timeout=30)

                    if response.status_code != 200:
                        logger.error(f"HTTP错误: {response.status_code}")
                        continue

                    result = response.json()
                    if "error_code" in result:
                        logger.error(f"百度API错误: {result}")
                        continue

                    if 'words_result' not in result or not result['words_result']:
                        logger.warning(f"百度OCR无结果(第{page_num}页)")
                        continue

                    words_result = result['words_result']
                    seller_name = words_result.get('SellerName', {})
                    if isinstance(seller_name, dict):
                        seller_name = seller_name.get('words', '')

                    invoice_type = words_result.get('InvoiceType', '')
                    if isinstance(invoice_type, dict):
                        invoice_type = invoice_type.get('words', '')

                    logger.info(f"百度OCR识别成功(第{page_num}页): 销售方={seller_name}, 类型={invoice_type}")
                    return words_result
                except Exception as e:
                    logger.error(f"百度OCR识别异常(第{page_num}页): {file_path}, 错误: {e}")
                    continue
        else:
            with open(file_path, 'rb') as f:
                image_base64 = base64.b64encode(f.read()).decode('utf-8')

            url = f"https://aip.baidubce.com/rest/2.0/ocr/v1/vat_invoice?access_token={access_token}"
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            payload = {"image": image_base64}

            logger.info("正在调用百度OCR API...")
            response = requests.post(url, data=payload, headers=headers, timeout=30)

            if response.status_code != 200:
                logger.error(f"HTTP错误: {response.status_code}")
                return None

            result = response.json()
            if "error_code" in result:
                logger.error(f"百度API错误: {result}")
                return None

            if 'words_result' not in result or not result['words_result']:
                logger.warning(f"百度OCR无结果: {file_path}")
                return None

            words_result = result['words_result']
            return words_result

    except Exception as e:
        logger.error(f"百度增值税发票识别异常: {file_path}, 错误: {e}")
        return None

    return None
