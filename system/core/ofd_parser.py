import zipfile
import xml.etree.ElementTree as ET
import re
import logging

from .data_utils import clean_amount, clean_date, clean_seller_name
from ..config import INVOICE_TEMPLATE

logger = logging.getLogger(__name__)


def is_ofd_file(file_path):
    return str(file_path).lower().endswith('.ofd')


def extract_invoice_from_ofd(file_path):
    try:
        with zipfile.ZipFile(file_path, 'r') as zf:
            result = _parse_ofd_standard(zf)
            if result:
                return result

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


def _parse_ofd_standard(zf):
    custom_data = _extract_custom_data(zf)
    page_texts = _extract_page_texts(zf)

    has_key_data = custom_data.get('发票号码') or custom_data.get('合计金额')
    if not has_key_data and not page_texts:
        return None

    record = dict(INVOICE_TEMPLATE)

    if custom_data.get('发票号码'):
        record['invoice_num'] = custom_data['发票号码'].strip()
    if custom_data.get('发票代码'):
        record['invoice_code'] = custom_data['发票代码'].strip()

    if custom_data.get('开票日期'):
        record['date'] = _parse_chinese_date(custom_data['开票日期'])

    if custom_data.get('销售方纳税人识别号'):
        record['seller_tax_id'] = custom_data['销售方纳税人识别号'].strip()
    if custom_data.get('购买方纳税人识别号'):
        record['buyer_tax_id'] = custom_data['购买方纳税人识别号'].strip()

    if custom_data.get('合计金额'):
        record['price_without_tax'] = clean_amount(custom_data['合计金额'])
    if custom_data.get('合计税额'):
        record['tax_amount'] = clean_amount(custom_data['合计税额'])
    if custom_data.get('价税合计'):
        record['total_amount'] = clean_amount(custom_data['价税合计'])
    elif record['price_without_tax'] and record['tax_amount']:
        try:
            record['total_amount'] = round(float(record['price_without_tax']) + float(record['tax_amount']), 2)
        except (ValueError, TypeError):
            pass

    if custom_data.get('发票类型'):
        record['invoice_type'] = custom_data['发票类型'].strip()
    else:
        record['invoice_type'] = '增值税电子普通发票'

    if custom_data.get('校验码'):
        record['check_code'] = custom_data['校验码'].strip()
    if custom_data.get('备注'):
        record['remark'] = custom_data['备注'].strip()

    _fill_from_page_texts(record, page_texts, custom_data)

    if not record.get('invoice_num') and not record.get('invoice_code'):
        logger.info("OFD标准格式解析：缺少发票号码和发票代码")
        return None

    try:
        amt = float(record.get('total_amount') or 0)
    except (ValueError, TypeError):
        amt = 0
    if amt <= 0:
        logger.info("OFD标准格式解析：缺少有效金额")
        return None

    details = _extract_details_from_page(page_texts, custom_data)

    logger.info(f"OFD标准格式解析完成: invoice_num={record.get('invoice_num')}, "
                f"seller={record.get('seller')}, amount={record.get('total_amount')}")
    return record, details


def _extract_custom_data(zf):
    custom_data = {}
    for xml_name in zf.namelist():
        if xml_name.upper() != 'OFD.XML':
            continue
        try:
            xml_content = zf.read(xml_name)
            root = ET.fromstring(xml_content)
            for elem in root.iter():
                tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
                if tag == 'CustomData':
                    name = elem.get('Name', '')
                    if name and elem.text and elem.text.strip():
                        custom_data[name.strip()] = elem.text.strip()
            break
        except Exception as e:
            logger.debug(f"解析OFD.xml失败: {e}")
            continue
    if custom_data:
        logger.info(f"从OFD.xml提取到CustomData: {list(custom_data.keys())}")
    return custom_data


def _extract_page_texts(zf):
    all_texts = []
    page_files = sorted([n for n in zf.namelist()
                         if n.lower().startswith('doc_') and '/pages/page_' in n.lower()
                         and n.lower().endswith('/content.xml')])

    for page_file in page_files:
        try:
            xml_content = zf.read(page_file)
            root = ET.fromstring(xml_content)
            page_texts = []
            for elem in root.iter():
                tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
                if tag == 'TextCode':
                    if elem.text and elem.text.strip():
                        text = elem.text.strip()
                        text = re.sub(r'\s+', '', text)
                        page_texts.append(text)
            if page_texts:
                all_texts.extend(page_texts)
        except Exception:
            continue

    if not all_texts:
        for xml_name in zf.namelist():
            if '/pages/' not in xml_name.lower() or not xml_name.lower().endswith('.xml'):
                continue
            try:
                xml_content = zf.read(xml_name)
                root = ET.fromstring(xml_content)
                for elem in root.iter():
                    tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
                    if tag == 'TextCode':
                        if elem.text and elem.text.strip():
                            text = elem.text.strip()
                            text = re.sub(r'\s+', '', text)
                            all_texts.append(text)
            except Exception:
                continue

    if all_texts:
        logger.info(f"从OFD页面中提取到 {len(all_texts)} 个文本片段")
    return all_texts


def _fill_from_page_texts(record, page_texts, custom_data):
    if not page_texts:
        return

    all_text = ' '.join(page_texts)

    if not record.get('invoice_num'):
        for text in page_texts:
            m = re.search(r'(\d{8,20})', text)
            if m and len(m.group(1)) >= 8:
                record['invoice_num'] = m.group(1)
                break

    if not record.get('date'):
        date = _extract_date_from_texts(page_texts)
        if date:
            record['date'] = date

    if not record.get('seller'):
        seller = _extract_seller_from_texts(page_texts, custom_data.get('销售方纳税人识别号', ''))
        if seller:
            record['seller'] = seller

    if not record.get('buyer'):
        buyer = _extract_buyer_from_texts(page_texts, custom_data.get('购买方纳税人识别号', ''))
        if buyer:
            record['buyer'] = buyer

    try:
        total_amt = float(record.get('total_amount') or 0)
    except (ValueError, TypeError):
        total_amt = 0
    if total_amt <= 0:
        amounts = _extract_amounts_from_texts(page_texts)
        if amounts:
            record['total_amount'] = amounts.get('total', record.get('total_amount', 0))
            try:
                price_amt = float(record.get('price_without_tax') or 0)
            except (ValueError, TypeError):
                price_amt = 0
            if price_amt <= 0:
                record['price_without_tax'] = amounts.get('price', record.get('price_without_tax', 0))
            try:
                tax_amt = float(record.get('tax_amount') or 0)
            except (ValueError, TypeError):
                tax_amt = 0
            if tax_amt <= 0:
                record['tax_amount'] = amounts.get('tax', record.get('tax_amount', 0))

    if not record.get('invoice_code'):
        for text in page_texts:
            if len(text) >= 10 and len(text) <= 12 and text.isdigit():
                if text != record.get('invoice_num', ''):
                    record['invoice_code'] = text
                    break

    if not record.get('tax_rate') or record['tax_rate'] == '0%':
        for text in page_texts:
            m = re.search(r'(\d+(?:\.\d+)?)%', text)
            if m:
                record['tax_rate'] = m.group(0)
                break

    if not record.get('item'):
        for text in page_texts:
            if any(kw in text for kw in ['服务', '货物', '技术', '咨询', '材料', '设备', '工程']):
                if len(text) >= 2 and len(text) <= 30:
                    record['item'] = text
                    break


def _extract_date_from_texts(texts):
    for text in texts:
        m = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', text)
        if m:
            return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
        m = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', text)
        if m:
            return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return ''


def _extract_seller_from_texts(texts, seller_tax_id=''):
    company_names = []
    for i, text in enumerate(texts):
        if len(text) >= 4 and not re.match(r'^[\d.%¥￥]+$', text):
            if not re.match(r'^\d{8,20}$', text):
                is_tax_id = re.match(r'^[A-Z0-9]{15,20}$', text)
                if not is_tax_id:
                    if any(kw in text for kw in ['有限', '公司', '集团', '企业', '商店', '经营部']):
                        company_names.append((i, text))

    if seller_tax_id and company_names:
        for idx, name in company_names:
            if idx + 1 < len(texts):
                next_text = texts[idx + 1]
                if next_text.replace(' ', '') == seller_tax_id.replace(' ', ''):
                    return clean_seller_name(name)

    if company_names:
        return clean_seller_name(company_names[-1][1])

    return ''


def _extract_buyer_from_texts(texts, buyer_tax_id=''):
    company_names = []
    for i, text in enumerate(texts):
        if len(text) >= 4 and not re.match(r'^[\d.%¥￥]+$', text):
            if not re.match(r'^\d{8,20}$', text):
                is_tax_id = re.match(r'^[A-Z0-9]{15,20}$', text)
                if not is_tax_id:
                    if any(kw in text for kw in ['有限', '公司', '集团', '企业', '商店', '经营部']):
                        company_names.append((i, text))

    if buyer_tax_id and company_names:
        for idx, name in company_names:
            if idx + 1 < len(texts):
                next_text = texts[idx + 1]
                if next_text.replace(' ', '') == buyer_tax_id.replace(' ', ''):
                    return clean_seller_name(name)

    if len(company_names) >= 2:
        return clean_seller_name(company_names[0][1])

    return ''


def _extract_amounts_from_texts(texts):
    amounts = {}
    found_amounts = []
    for text in texts:
        if '¥' in text or '￥' in text:
            clean = text.replace('¥', '').replace('￥', '').replace(',', '').strip()
            m = re.search(r'(\d+\.?\d*)', clean)
            if m:
                try:
                    val = float(m.group(1))
                    if val > 0:
                        found_amounts.append(val)
                except ValueError:
                    continue

    if not found_amounts:
        for text in texts:
            m = re.search(r'(\d{1,3}(?:,\d{3})*\.\d{2})', text)
            if m:
                try:
                    val = float(m.group(1).replace(',', ''))
                    if val > 0:
                        found_amounts.append(val)
                except ValueError:
                    continue

    if found_amounts:
        amounts['total'] = max(found_amounts)
        found_amounts.remove(max(found_amounts))
        if found_amounts:
            amounts['tax'] = min(found_amounts)
            amounts['price'] = amounts.get('total', 0) - amounts.get('tax', 0)
        else:
            amounts['price'] = amounts.get('total', 0)

    return amounts


def _extract_details_from_page(page_texts, custom_data):
    details = []
    if not page_texts:
        return details

    item_indices = []
    for i, text in enumerate(page_texts):
        if any(kw in text for kw in ['服务', '货物', '技术', '咨询', '材料', '设备', '工程', '租赁', '维修', '运输']):
            if len(text) >= 2 and len(text) <= 30:
                if not re.match(r'^[\d.%¥￥]+$', text):
                    item_indices.append(i)

    for idx in item_indices:
        item_name = page_texts[idx]
        tax_rate = ''
        amount = 0.0
        tax_amount = 0.0

        for j in range(idx + 1, min(idx + 6, len(page_texts))):
            text = page_texts[j]
            rate_m = re.search(r'(\d+(?:\.\d+)?)%', text)
            if rate_m and not tax_rate:
                tax_rate = rate_m.group(0)
                continue
            amt_m = re.search(r'[\d,]+\.?\d*', text.replace('¥', '').replace('￥', '').replace(',', ''))
            if amt_m:
                try:
                    val = float(amt_m.group())
                    if val > 0:
                        if amount == 0.0:
                            amount = val
                        elif tax_amount == 0.0 and val < amount:
                            tax_amount = val
                except ValueError:
                    continue

        if item_name and (amount > 0 or tax_rate):
            details.append({
                'item_name': item_name,
                'tax_rate': tax_rate,
                'amount': round(amount, 2),
                'tax_amount': round(tax_amount, 2),
            })

    return details


def _parse_chinese_date(date_str):
    m = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', date_str)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return clean_date(date_str)


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
        upper_name = xml_name.upper()
        if upper_name.endswith('OFD.XML') or '/PAGES/' in upper_name or '/TPLS/' in upper_name:
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

    record = dict(INVOICE_TEMPLATE)

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

    record = dict(INVOICE_TEMPLATE)

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

    record = dict(INVOICE_TEMPLATE)
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
