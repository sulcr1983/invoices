import re
import hashlib
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def calculate_file_md5(file_path):
    md5_hash = hashlib.md5()
    try:
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                md5_hash.update(chunk)
        return md5_hash.hexdigest()
    except Exception as e:
        logger.error(f"计算文件MD5失败: {file_path}, 错误: {e}")
        return None


def clean_amount(amount_str):
    if not amount_str:
        return 0.00
    cleaned = re.sub(r'[^\d.-]', '', str(amount_str))
    try:
        return round(float(cleaned), 2)
    except ValueError:
        return 0.00


def clean_date(date_str):
    if not date_str:
        return ""
    date_str = date_str.strip()
    for pattern, fmt in [
        (r'(\d{8})', None),
        (r'(\d{4})[\-/年](\d{1,2})[\-/月](\d{1,2})', None),
        (r'(\d{4})年(\d{1,2})月(\d{1,2})日', None),
    ]:
        m = re.search(pattern, date_str)
        if m:
            try:
                if pattern == r'(\d{8})':
                    y, mth, d = int(m.group(1)[:4]), int(m.group(1)[4:6]), int(m.group(1)[6:8])
                else:
                    y, mth, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                if 1 <= mth <= 12 and 1 <= d <= 31:
                    return f"{y}-{mth:02d}-{d:02d}"
            except:
                pass
    return ""


def is_valid_date(date_str):
    if not date_str:
        return False
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False


def clean_seller_name(seller):
    if not seller:
        return ""
    seller = re.sub(r'[\\/:*?"<>|]', '_', seller)
    return seller.strip()


def safe_get_field(text, pattern, group_idx=1, default=""):
    try:
        match = re.search(pattern, text)
        if match:
            return match.group(group_idx)
        return default
    except Exception as e:
        logger.debug(f"字段提取异常: pattern={pattern}, error={e}")
        return default
