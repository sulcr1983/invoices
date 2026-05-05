# 技术债务归档

> 扫描时间: 2026-05-05 | 版本: v5.2

## P1 - 高优先级（建议近期处理）

### 1. sys.path Hack 模式（8个文件）
- **位置**: `core/baidu_ocr.py`, `core/invoice_parser.py`, `core/text_invoice_parser.py`, `core/pipeline.py`, `routes/shared.py`, `db_manager.py`, `main.py`, `system/api_server.py`
- **问题**: 每个文件都有 `_THIS_DIR` / `_PARENT_DIR` + `sys.path.insert` hack，以及双重 `try/except ImportError` 导入模式（超过20处）
- **影响**: 包结构不规范，IDE无法正确推断模块关系
- **建议**: 通过正确的 `__init__.py` 和 `pip install -e .` 解决，统一使用相对导入

### 2. 猴子补丁 (Monkey Patching) 模式
- **位置**: `database/models.py:233`, `database/queries.py:344`, `database/writes.py:201`, `database/webhooks.py:170`, `database/locks.py:78`
- **问题**: 所有 DBManager 方法通过猴子补丁附加，IDE无法推断方法列表，新开发者难以定位
- **建议**: 重构为正常的类继承或 Mixin 模式

### 3. RECORD_COLUMNS 重复定义（3处）
- **位置**: `database/queries.py:274`, `database/webhooks.py:12`, `webhook_manager.py:18`
- **问题**: 同一常量在3个文件中独立定义，任何字段变更需同时修改三处
- **建议**: 提取到 `database/connection.py` 或 `database/models.py` 作为单一数据源

## P2 - 中优先级（有空时处理）

### 4. 未使用的函数（12个）
- `database/queries.py`: `get_invoice_nums_ordered`, `record_exists`, `record_exists_by_md5`, `get_pending_count`, `get_unsynced_records`, `get_unsynced_records_as_dicts`, `get_pending_push_records`
- `database/writes.py`: `insert_record`, `update_sync_status`
- `database/webhooks.py`: `row_to_dict`, `get_webhook_push_failed`
- `database/locks.py`: `is_file_locked`
- `services/file_service.py`: `move_to_done`
- **建议**: 确认无外部调用后删除，或标记为预留接口

### 5. 异步推送死代码
- **位置**: `webhook_manager.py:95-152` (`async_push_single_webhook`), `webhook_manager.py:185-218` (`async_push_to_all_webhooks`)
- **问题**: 完整的异步推送实现，但从未被调用，所有推送走同步路径
- **建议**: 删除，或改为实际使用异步推送

### 6. INVOICE_TEMPLATE 无意义守卫
- **位置**: `invoice_parser.py:87`, `ofd_parser.py:59/450/539/607`, `text_invoice_parser.py:29`
- **问题**: `{k: v if v != "" else "" for k, v in INVOICE_TEMPLATE.items()}` 条件永远返回 `v` 本身
- **建议**: 简化为 `dict(INVOICE_TEMPLATE)` 或 `{k: v for k, v in INVOICE_TEMPLATE.items()}`

### 7. 数据库连接未使用上下文管理器
- **位置**: `database/` 子包所有方法
- **问题**: 手动 `conn = self._get_connection()` + `conn.close()`，异常时可能连接泄漏
- **建议**: 统一使用 `with` 上下文管理器

### 8. 裸 except 使用
- **位置**: `invoice_parser.py:62`, `text_invoice_parser.py:87`
- **问题**: 使用 `except:` 而非 `except Exception:`，可能捕获 SystemExit 等不应捕获的异常
- **建议**: 改为 `except Exception:`

## P3 - 低优先级（可延后）

### 9. SQL 拼接模式
- **位置**: `database/queries.py:66`
- **问题**: 使用 f-string 构建 SQL `ORDER BY` 子句，虽有白名单校验但模式不理想
- **建议**: 使用参数化查询或ORM

### 10. OFD 明细行提取未实现
- **位置**: `core/ofd_parser.py:345-347` (`_extract_details_from_page`)
- **问题**: 空实现存根函数，仅返回空列表
- **建议**: 实现OFD发票明细行提取，或从页面TextObject中解析

### 11. .env 中 os.environ 重复调用
- **位置**: `config.py` 全文
- **问题**: 每个配置项都调用 `__import__('os').environ.get()`，不够优雅
- **建议**: 顶部 `import os` 后统一使用 `os.environ.get()`
