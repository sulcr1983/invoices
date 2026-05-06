# 技术债务归档

> 扫描时间: 2026-05-05 | 版本: v6.0 | 状态: 全部已处理 ✅

## P1 - 高优先级 ✅ 全部已处理

### 1. sys.path Hack 模式 ✅
- **位置**: 10个文件
- **原问题**: 每个文件都有 `_THIS_DIR` / `_PARENT_DIR` + `sys.path.insert` hack，以及双重 `try/except ImportError` 导入模式
- **处理**: 全部改为相对导入，删除所有 `sys.path.insert` 和 `except ImportError` fallback
- **涉及文件**: `baidu_ocr.py`, `invoice_parser.py`, `text_invoice_parser.py`, `ofd_parser.py`, `pipeline.py`, `routes/shared.py`, `routes/system.py`, `routes/tasks.py`, `routes/dashboard.py`, `db_manager.py`, `main.py`, `api_server.py`, `extractor.py`, `file_service.py`, `webhook_payload.py`, `invoice_service.py`, `sync_service.py`

### 2. 猴子补丁 (Monkey Patching) 模式 ✅
- **原问题**: 所有 DBManager 方法通过猴子补丁附加
- **处理**: 重构为 Mixin 类继承模式
  - `models.py` → `ModelsMixin`
  - `queries.py` → `QueriesMixin`
  - `writes.py` → `WritesMixin`
  - `webhooks.py` → `WebhooksMixin`
  - `locks.py` → `LocksMixin`
  - `connection.py` → `DBManager(ModelsMixin, QueriesMixin, WritesMixin, WebhooksMixin, LocksMixin)`

### 3. RECORD_COLUMNS 重复定义 ✅
- **原问题**: 同一常量在3个文件中独立定义
- **处理**: 提取到 `database/columns.py` 作为单一数据源，所有引用统一从此处导入

## P2 - 中优先级 ✅ 全部已处理

### 4. 未使用的函数 ✅
- **处理**: 已删除12个未使用函数（上一轮已完成）

### 5. 异步推送死代码 ✅
- **处理**: 已删除 `async_push_single_webhook` 和 `async_push_to_all_webhooks`（上一轮已完成）

### 6. INVOICE_TEMPLATE 无意义守卫 ✅
- **处理**: 全部7处替换为 `dict(INVOICE_TEMPLATE)`

### 7. 数据库连接上下文管理器 ✅
- **处理**: 添加 `_ConnectionContext` 上下文管理器，`queries.py`/`writes.py`/`webhooks.py` 全部改用 `with self.connection() as conn:`

### 8. 裸 except 使用 ✅
- **处理**: 4处 `except:` 改为 `except Exception:`（上一轮已完成）

## P3 - 低优先级 ✅ 全部已处理

### 9. SQL 拼接模式 ✅
- **处理**: ORDER BY 已有白名单校验（`safe_order_cols`），`get_distinct_values` 也有白名单（`safe_cols`），LIMIT/OFFSET 使用 `int()` 转换。当前实现已安全。

### 10. OFD 明细行提取 ✅
- **处理**: 实现 `_extract_details_from_page()`，从页面 TextCode 中提取项目名称、税率、金额、税额

### 11. config.py os.environ 重复调用 ✅
- **处理**: 顶部添加 `import os`，所有 `__import__('os').environ.get()` 替换为 `os.environ.get()`

## 回归测试结果

- 后端压力测试: **55/55 通过**
- API 接口测试: **75/75 通过**
- E2E Web 界面: **正常**（仪表盘、发票台账、搜索功能均正常）

---

## 本次清理 (2026-05-07 / /neat)

### 已清理
1. **重复 claude.md**: 删除根目录小写 `claude.md`（与 `CLAUDE.md` 内容一致）
2. **config.py 死 import**: 删除 `import sys`（未被引用）
3. **invoices.py 死 import**: 删除 `verify_invoice_mock` 导入（未被使用）
4. **database/records.py**: 删除无任何引用的文件（仅重导出 queries/writes）
5. **VERIFY_STATUS_LABELS 去重**: 删除 `invoices.py` 中的重复定义，改为从 `core/verify.py` 导入
6. **README 同步**: 功能清单/更新记录/测试命令与代码同步

### 建议重构清单
| 位置 | 建议 | 优先级 |
|------|------|--------|
| `routes/invoices.py:59` | 字段命名不一致：列表API用 `certification_status` 映射DB的 `deduction_status`，详情API直接返回原始字段名 `deduction_status`。前端能兼容但易混淆 | P3 |
| `routes/invoices.py` 多处 | `deduction_status` 在列表API中被重复使用为"到期状态"(expired/expiring/normal)，同时 DB 同名字段表示"认证状态"(certified/unverified)，语义过载 | P3 |
