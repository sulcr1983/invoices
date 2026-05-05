import zipfile
import xml.etree.ElementTree as ET
import re
import logging
from io import BytesIO

try:
    from .data_utils import clean_amount, clean_date, clean_seller_name
except ImportError:
    from core.data_utils import clean_amount, clean_date, clean_seller_name

try:
    from ..config import INVOICE_TEMPLATE
except ImportError:
    from config import INVOICE_TEMPLATE

logger = logging.getLogger(__name__)


def is_ofd_file(file_path):
    return str(file_path).lower().endswith('.ofd')


def extract_invoice_from_ofd(file_path):
    try:
        with zipfile.ZipFile(file_path, 'r') as zf:
            result = _parse_embedded_xml(zf)
            if result:
                return result

            images = _extract_images_from_ofd(zf)
            if images:
                return 'OCR_NEEDED', images

            logger.warning(f"OFD文件中未找到发票数据: {file_path}")
            return None
    except zipfile.BadZipFile:
        logger.error(f"OFD文件格式无效(非ZIP格式): {file_path}")
        return None
    except Exception as e:
        logger.error(f"OFD文件解析异常: {file_path}, 错误: {e}")
        return None


def _parse_embedded_xml(zf):
    xml_candidates = []
    for name in zf.namelist():
        if name.lower().endswith('.xml'):
            xml_candidates.append(name)

    priority_patterns = [
        r'[Aa]ttach(?:ment)?s?[/\\].*\.xml$',
        r'[Aa]ttachs?[/\\].*\.xml$',
        r'(?:invoice|einvoice|original).*\.xml$',
    ]

    for pattern in priority_patterns:
        for xml_name in xml_candidates:
            if re.search(pattern, xml_name, re.IGNORECASE):
                try:
                    xml_content = zf.read(xml_name)
                    result = _parse_invoice_xml(xml_content)
                    if result:
                        logger.info(f"从OFD附件解析发票成功: {xml_name}")
                        return result
                except Exception as e:
                    logger.debug(f"解析OFD中的XML失败: {xml_name}, 错误: {e}")
                    continue

    for xml_name in xml_candidates:
        if xml_name.upper().endswith('OFD.XML'):
            continue
        try:
            xml_content = zf.read(xml_name)
            if len(xml_content) < 50:
                continue
            result = _parse_invoice_xml(xml_content)
            if result:
                logger.info(f"从OFD解析发票成功: {xml_name}")
                return result
        except Exception:
            continue

    return None


def _parse_invoice_xml(xml_content):
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        return None

    result = _parse_tax_bureau_format(root)
    if result:
        return result

    result = _parse_einvoice_format(root)
    if result:
        return result

    result = _parse_flat_format(root)
    if result:
        return result

    return None


def _find_text(root, *paths):
    for path in paths:
        elem = root.find(path)
        if elem is not None and elem.text and elem.text.strip():
            return elem.text.strip()
    return ''


def _find_text_recursive(root, tag_name):
    for elem in root.iter():
        if elem.tag.endswith(tag_name) or elem.tag == tag_name:
            if elem.text and elem.text.strip():
                return elem.text.strip()
    return ''


def _parse_tax_bureau_format(root):
    fpdm = _find_text_recursive(root, 'fpdm')
    fphm = _find_text_recursive(root, 'fphm')
    if not fpdm and not fphm:
        return None

    record = {k: v if v != "" else "" for k, v in INVOICE_TEMPLATE.items()}

    record['invoice_code'] = fpdm
    record['invoice_num'] = fphm
    record['date'] = clean_date(_find_text_recursive(root, 'kprq'))
    record['seller'] = clean_seller_name(_find_text_recursive(root, 'xfmc'))
    record['seller_tax_id'] = _find_text_recursive(root, 'xfsbh')
    record['buyer'] = _find_text_recursive(root, 'gfmc')
    record['buyer_tax_id'] = _find_text_recursive(root, 'gfsbh')
    record['total_amount'] = clean_amount(_find_text_recursive(root, 'jshj'))
    record['price_without_tax'] = clean_amount(_find_text_recursive(root, 'hjje'))
    record['tax_amount'] = clean_amount(_find_text_recursive(root, 'hjse'))

    tax_rate = _find_text_recursive(root, 'sl')
    if tax_rate:
        if '%' not in tax_rate:
            try:
                rv = float(tax_rate)
                if rv < 1:
                    rv *= 100
                tax_rate = f"{rv}%"
            except ValueError:
                pass
        record['tax_rate'] = tax_rate
    else:
        record['tax_rate'] = "0%"

    record['check_code'] = _find_text_recursive(root, 'jym')
    record['remark'] = _find_text_recursive(root, 'bz')

    fptype = _find_text_recursive(root, 'fptype')
    if fptype:
        type_map = {
            '026': '增值税电子普通发票',
            '028': '增值税电子专用发票',
            '004': '增值税专用发票',
            '007': '增值税普通发票',
            '010': '增值税普通发票(卷票)',
            '011': '增值税电子普通发票(通行费)',
        }
        record['invoice_type'] = type_map.get(fptype, fptype)
    else:
        record['invoice_type'] = _find_text_recursive(root, 'fptype_mc') or '增值税电子普通发票'

    item_name = _find_text_recursive(root, 'fwmc') or _find_text_recursive(root, 'spmc')
    record['item'] = item_name

    details = []
    detail_nodes = []
    for elem in root.iter():
        tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
        if tag in ('fyxm', 'spxx', 'detail', 'Detail', 'GoodsDetail'):
            detail_nodes.append(elem)

    if detail_nodes:
        for node in detail_nodes:
            d_item = _find_text_recursive(node, 'fwmc') or _find_text_recursive(node, 'spmc') or ''
            d_rate = _find_text_recursive(node, 'sl') or ''
            d_amount = clean_amount(_find_text_recursive(node, 'je') or '0')
            d_tax = clean_amount(_find_text_recursive(node, 'se') or '0')
            if d_item or d_amount > 0:
                if d_rate and '%' not in d_rate:
                    try:
                        rv = float(d_rate)
                        if rv < 1:
                            rv *= 100
                        d_rate = f"{rv}%"
                    except ValueError:
                        pass
                details.append({
                    'item_name': d_item,
                    'tax_rate': d_rate,
                    'amount': d_amount,
                    'tax_amount': d_tax,
                })

    logger.info(f"OFD税务格式解析完成: invoice_num={record.get('invoice_num')}, seller={record.get('seller')}")
    return record, details


def _parse_einvoice_format(root):
    invoice_code = _find_text_recursive(root, 'InvoiceCode')
    invoice_num = _find_text_recursive(root, 'InvoiceNumber')
    if not invoice_code and not invoice_num:
        return None

    if _find_text_recursive(root, 'fpdm') or _find_text_recursive(root, 'fphm'):
        return None

    record = {k: v if v != "" else "" for k, v in INVOICE_TEMPLATE.items()}

    record['invoice_code'] = invoice_code
    record['invoice_num'] = invoice_num
    record['date'] = clean_date(_find_text_recursive(root, 'InvoiceDate'))
    record['seller'] = clean_seller_name(
        _find_text_recursive(root, 'SellerName') or _find_text_recursive(root, 'Seller') or ''
    )
    record['seller_tax_id'] = _find_text_recursive(root, 'SellerTaxID') or _find_text_recursive(root, 'SellerRegisterNum')
    record['buyer'] = _find_text_recursive(root, 'BuyerName') or _find_text_recursive(root, 'PurchaserName') or ''
    record['buyer_tax_id'] = _find_text_recursive(root, 'BuyerTaxID') or _find_text_recursive(root, 'PurchaserRegisterNum')
    record['total_amount'] = clean_amount(
        _find_text_recursive(root, 'TotalAmount') or _find_text_recursive(root, 'AmountInFiguers') or '0'
    )
    record['price_without_tax'] = clean_amount(
        _find_text_recursive(root, 'AmountWithoutTax') or '0'
    )
    record['tax_amount'] = clean_amount(_find_text_recursive(root, 'TotalTax') or '0')

    tax_rate = _find_text_recursive(root, 'TaxRate') or _find_text_recursive(root, 'CommodityTaxRate') or ''
    if tax_rate:
        if '%' not in tax_rate:
            try:
                rv = float(tax_rate)
                if rv < 1:
                    rv *= 100
                tax_rate = f"{rv}%"
            except ValueError:
                pass
        record['tax_rate'] = tax_rate
    else:
        record['tax_rate'] = "0%"

    record['check_code'] = _find_text_recursive(root, 'CheckCode')
    record['remark'] = _find_text_recursive(root, 'Remark') or _find_text_recursive(root, 'Remarks')
    record['invoice_type'] = _find_text_recursive(root, 'InvoiceTypeOrg') or _find_text_recursive(root, 'InvoiceType') or ''
    record['item'] = _find_text_recursive(root, 'CommodityName') or _find_text_recursive(root, 'ItemName') or ''

    details = []
    logger.info(f"OFD电子发票格式解析完成: invoice_num={record.get('invoice_num')}, seller={record.get('seller')}")
    return record, details


def _parse_flat_format(root):
    all_text = ET.tostring(root, encoding='unicode', method='text')
    has_invoice_markers = any(kw in all_text for kw in ['发票号码', '发票代码', '价税合计', '销售方'])
    if not has_invoice_markers:
        return None

    def extract_by_keyword(text, *keywords):
        for kw in keywords:
            patterns = [
                rf'{kw}\s*[：:]\s*([^\s,，\n]+)',
                rf'{kw}\s*=\s*"([^"]+)"',
                rf'<{kw}>([^<]+)</{kw}>',
            ]
            for pattern in patterns:
                m = re.search(pattern, text)
                if m:
                    return m.group(1).strip()
        return ''

    raw = all_text
    invoice_num = extract_by_keyword(raw, '发票号码', 'InvoiceNum', 'fphm')
    invoice_code = extract_by_keyword(raw, '发票代码', 'InvoiceCode', 'fpdm')
    if not invoice_num and not invoice_code:
        return None

    record = {k: v if v != "" else "" for k, v in INVOICE_TEMPLATE.items()}
    record['invoice_num'] = invoice_num
    record['invoice_code'] = invoice_code
    record['date'] = clean_date(extract_by_keyword(raw, '开票日期', 'InvoiceDate', 'kprq'))
    record['seller'] = clean_seller_name(extract_by_keyword(raw, '销售方', 'SellerName', 'xfmc'))
    record['seller_tax_id'] = extract_by_keyword(raw, '销售方纳税识别号', 'SellerRegisterNum', 'xfsbh')
    record['buyer'] = extract_by_keyword(raw, '购买方', 'PurchaserName', 'gfmc')
    record['buyer_tax_id'] = extract_by_keyword(raw, '购买方纳税识别号', 'PurchaserRegisterNum', 'gfsbh')
    record['total_amount'] = clean_amount(extract_by_keyword(raw, '价税合计', 'TotalAmount', 'jshj'))
    record['price_without_tax'] = clean_amount(extract_by_keyword(raw, '不含税金额', 'AmountWithoutTax', 'hjje'))
    record['tax_amount'] = clean_amount(extract_by_keyword(raw, '税额', 'TotalTax', 'hjse'))
    record['check_code'] = extract_by_keyword(raw, '校验码', 'CheckCode', 'jym')
    record['remark'] = extract_by_keyword(raw, '备注', 'Remark', 'bz')
    record['invoice_type'] = extract_by_keyword(raw, '发票类型', 'InvoiceType', 'fptype') or '增值税电子普通发票'
    record['item'] = extract_by_keyword(raw, '项目名称', 'CommodityName', 'spmc')

    tax_rate = extract_by_keyword(raw, '税率', 'TaxRate', 'sl')
    if tax_rate:
        if '%' not in tax_rate:
            try:
                rv = float(tax_rate)
                if rv < 1:
                    rv *= 100
                tax_rate = f"{rv}%"
            except ValueError:
                pass
        record['tax_rate'] = tax_rate

    logger.info(f"OFD通用格式解析完成: invoice_num={record.get('invoice_num')}")
    return record, []


def _extract_images_from_ofd(zf):
    images = []
    for name in zf.namelist():
        lower_name = name.lower()
        if lower_name.endswith(('.png', '.jpg', '.jpeg', '.bmp')):
            try:
                img_data = zf.read(name)
                if len(img_data) > 500:
                    images.append(img_data)
            except Exception:
                continue
    if images:
        logger.info(f"从OFD中提取到 {len(images)} 张图片，可用于OCR识别")
    return images
