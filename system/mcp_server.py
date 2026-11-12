#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SuperSu 发票系统 · 本地 MCP Server（零第三方依赖）

把台账以只读工具的形式暴露给支持 MCP 的 AI 客户端（如 WorkBuddy / Claude Desktop）。

用法（在 MCP 客户端里配置 stdio 启动）：
    python D:/test/invoices/system/mcp_server.py

实现的协议：JSON-RPC 2.0 over stdio，MCP protocolVersion 2024-11-05
支持方法：initialize / notifications/initialized / tools/list / tools/call / ping

安全说明：全部工具只读，不提供写入、删除、验真等有副作用的能力。
"""

import json
import sys
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from system.config import DB_PATH  # noqa: E402
from system.db_manager import DBManager  # noqa: E402

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "supersu-invoice", "version": "1.0.0"}

_db = DBManager(DB_PATH)


def _log(msg):
    """日志只能写 stderr，stdout 是协议通道。"""
    print(f"[mcp] {msg}", file=sys.stderr, flush=True)


# ---------------- tools ----------------

TOOLS = [
    {
        "name": "list_invoices",
        "description": "按关键词/日期范围查询发票台账，返回精简字段列表。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "发票号/销售方/项目关键词"},
                "date_from": {"type": "string", "description": "开票日期起，YYYY-MM-DD"},
                "date_to": {"type": "string", "description": "开票日期止，YYYY-MM-DD"},
                "limit": {"type": "integer", "description": "返回条数，默认 20，最大 200"},
            },
        },
    },
    {
        "name": "get_invoice",
        "description": "按发票号码查询单张发票的完整信息。",
        "inputSchema": {
            "type": "object",
            "properties": {"invoice_num": {"type": "string"}},
            "required": ["invoice_num"],
        },
    },
    {
        "name": "get_stats",
        "description": "按日期范围汇总：张数、价税合计、不含税金额、税额、销售方数量。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "date_from": {"type": "string"},
                "date_to": {"type": "string"},
            },
        },
    },
    {
        "name": "list_duplicates",
        "description": "列出被拦截的重复发票记录。",
        "inputSchema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "description": "默认 20"}},
        },
    },
    {
        "name": "list_risks",
        "description": "列出被标记为异常的发票（大额/疑似拆票/超期等）。",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def _clamp_limit(value, default=20, maximum=200):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(n, maximum))


def tool_list_invoices(args):
    records, total = _db.query_records(
        keyword=args.get("keyword"),
        date_from=args.get("date_from"),
        date_to=args.get("date_to"),
        limit=_clamp_limit(args.get("limit")),
        offset=0,
    )
    items = [{
        "invoice_num": r.get("invoice_num"),
        "date": r.get("date"),
        "seller": r.get("seller"),
        "total_amount": r.get("total_amount"),
        "invoice_type": r.get("invoice_type"),
        "verify_status": r.get("verify_status"),
        "risk_flags": r.get("risk_flags"),
    } for r in records]
    return {"total": total, "returned": len(items), "invoices": items}


def tool_get_invoice(args):
    num = args.get("invoice_num", "")
    record = _db.get_record_by_invoice_num(num)
    if not record:
        return {"found": False, "message": "发票不存在"}
    keys = ["invoice_num", "invoice_code", "date", "seller", "seller_tax_id", "buyer",
            "buyer_tax_id", "item", "price_without_tax", "tax_rate", "tax_amount",
            "total_amount", "invoice_type", "remark", "verify_status", "deduction_status",
            "department", "project", "expense_type", "risk_flags"]
    return {"found": True, "invoice": {k: record.get(k) for k in keys}}


def tool_get_stats(args):
    where, params = "", []
    if args.get("date_from"):
        where += " AND date >= ?"
        params.append(args["date_from"])
    if args.get("date_to"):
        where += " AND date <= ?"
        params.append(args["date_to"])
    with _db.connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*), COALESCE(SUM(total_amount),0), COALESCE(SUM(price_without_tax),0), "
            f"COALESCE(SUM(tax_amount),0), COUNT(DISTINCT seller) FROM records WHERE 1=1 {where}", params)
        row = cur.fetchone()
    return {
        "count": row[0],
        "total_amount": round(row[1], 2),
        "price_without_tax": round(row[2], 2),
        "tax_amount": round(row[3], 2),
        "seller_count": row[4],
        "date_from": args.get("date_from"),
        "date_to": args.get("date_to"),
    }


def tool_list_duplicates(args):
    records, total = _db.get_duplicate_records(limit=_clamp_limit(args.get("limit")), offset=0)
    return {"total": total, "records": records}


def tool_list_risks(args):
    with _db.connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT invoice_num, seller, total_amount, date, risk_flags
            FROM records WHERE risk_flags IS NOT NULL AND risk_flags != ''
            ORDER BY total_amount DESC LIMIT 50
        """)
        rows = cur.fetchall()
    return {"count": len(rows), "items": [
        {"invoice_num": r[0], "seller": r[1], "total_amount": r[2], "date": r[3], "risk_flags": r[4]}
        for r in rows
    ]}


HANDLERS = {
    "list_invoices": tool_list_invoices,
    "get_invoice": tool_get_invoice,
    "get_stats": tool_get_stats,
    "list_duplicates": tool_list_duplicates,
    "list_risks": tool_list_risks,
}


# ---------------- JSON-RPC ----------------

def _reply(msg_id, result=None, error=None):
    payload = {"jsonrpc": "2.0", "id": msg_id}
    if error is not None:
        payload["error"] = error
    else:
        payload["result"] = result
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def handle(msg):
    method = msg.get("method")
    msg_id = msg.get("id")

    if method == "initialize":
        return _reply(msg_id, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": SERVER_INFO,
        })

    if method in ("notifications/initialized", "initialized"):
        return  # 通知不需要回包

    if method == "ping":
        return _reply(msg_id, {})

    if method == "tools/list":
        return _reply(msg_id, {"tools": TOOLS})

    if method == "tools/call":
        params = msg.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        handler = HANDLERS.get(name)
        if not handler:
            return _reply(msg_id, error={"code": -32601, "message": f"未知工具: {name}"})
        try:
            result = handler(args)
            return _reply(msg_id, {
                "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}],
                "isError": False,
            })
        except Exception as e:
            _log(f"工具 {name} 执行失败: {e}")
            return _reply(msg_id, {
                "content": [{"type": "text", "text": f"执行失败: {e}"}],
                "isError": True,
            })

    if msg_id is not None:
        return _reply(msg_id, error={"code": -32601, "message": f"未实现的方法: {method}"})


def main():
    _log(f"SuperSu MCP Server 启动，DB={DB_PATH}")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            _log(f"非法 JSON: {line[:80]}")
            continue
        try:
            handle(msg)
        except Exception as e:
            _log(f"处理消息异常: {e}")
            if msg.get("id") is not None:
                _reply(msg.get("id"), error={"code": -32603, "message": str(e)})


if __name__ == "__main__":
    main()
