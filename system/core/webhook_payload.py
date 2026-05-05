import logging
try:
    from ..config import INVOICE_FIELD_NAMES
except ImportError:
    from config import INVOICE_FIELD_NAMES

logger = logging.getLogger(__name__)


def _str(val):
    if val is None:
        return ""
    return str(val).strip()


def _amount(val):
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    cleaned = str(val).replace("￥", "").replace("¥", "").replace(",", "").strip()
    try:
        return float(cleaned)
    except (ValueError, AttributeError):
        return 0.0


FIELD_KEYS = [
    ("invoice_num", "str"), ("seller", "str"), ("seller_tax_id", "str"),
    ("date", "str"), ("buyer", "str"), ("buyer_tax_id", "str"),
    ("item", "str"), ("price_without_tax", "amount"), ("tax_rate", "str"),
    ("tax_amount", "amount"), ("total_amount", "amount"),
    ("invoice_code", "str"), ("check_code", "str"),
    ("invoice_type", "str"), ("remark", "str"),
]


def _normalize_text(text):
    if text is None:
        return ""
    return str(text).replace(" ", "").replace("\u3000", "").replace("\u00a0", "")


def _build_fields(record_dict, reverse_schema=None):
    fields = {}
    norm_reverse = {}
    if reverse_schema is not None:
        for cn_name, fid in reverse_schema.items():
            norm_reverse[_normalize_text(cn_name)] = fid

    for key, ftype in FIELD_KEYS:
        cn_name = INVOICE_FIELD_NAMES.get(key, key)
        raw = record_dict.get(key, "")
        val = _amount(raw) if ftype == "amount" else _str(raw)
        if reverse_schema is not None:
            field_id = norm_reverse.get(_normalize_text(cn_name))
            if field_id:
                fields[field_id] = val

    if reverse_schema is not None:
        for cn_name, fid in reverse_schema.items():
            norm_cn = _normalize_text(cn_name)
            if norm_cn not in norm_reverse or fid not in fields:
                if fid not in fields:
                    default_val = _get_default_for_extra_field(cn_name)
                    if default_val is not None:
                        fields[fid] = default_val
    return fields


def _get_default_for_extra_field(cn_name):
    if "状态" in cn_name or "处理" in cn_name:
        return [{"text": "AI自动导入"}]
    if "金额" in cn_name or "税额" in cn_name or "价税" in cn_name:
        return 0.0
    if "税率" in cn_name:
        return ""
    return ""


def build_wecom_payload(record_dict, schema_json):
    schema = schema_json
    if isinstance(schema_json, dict):
        if "schema" in schema_json and isinstance(schema_json["schema"], dict):
            schema = schema_json["schema"]
        elif "add_records" in schema_json:
            schema = {}

    reverse = {}
    for k, v in schema.items():
        if isinstance(v, str):
            reverse[v] = k
        elif isinstance(v, dict) and v:
            reverse[str(v)] = k
    values = _build_fields(record_dict, reverse_schema=reverse)
    return {"add_records": [{"values": values}]}


PAYLOAD_BUILDERS = {"wecom": build_wecom_payload}
PLATFORM_LABELS = {"wecom": "企微"}
