# SuperSu 发票处理系统 · AI 协作说明

> 本文件供 AI 编码助手阅读。只写**这个项目真实的样子**，不写通用模板。

## 一句话

本地运行的个人发票处理工具：拖入 PDF/OFD/图片 → 识别 → 去重 → 归档 → 台账 → 统计。
自用场景，单机部署，无账号体系。

## 真实技术栈

| 层 | 实际选型 |
|:--|:--|
| Web | Flask 3.x（Blueprint，路径以 `/api/` 开头） |
| 数据 | SQLite（`system/data/invoices.db`，WAL 模式）+ `发票台账.csv` |
| 前端 | 原生 HTML/CSS/JS + ECharts（无构建链，无框架） |
| 识别 | OFD 内嵌 XML → 百度 OCR（可选）→ pdfplumber → RapidOCR（离线兜底） |
| 去重 | MD5 → 发票号唯一索引 → RapidFuzz 模糊相似 |
| 测试 | pytest（`system/tests/test_api.py`）+ 手工压测脚本 |

**没有**：Pydantic、SQLAlchemy、Celery/队列、多租户、RLS、API 版本化前缀、前端构建工具。

## 目录

```
api_server.py          根入口（读 INVOICE_HOST / INVOICE_PORT）
system/api_server.py   Flask 应用工厂（初始化日志、DB 备份）
system/routes/         dashboard / invoices / stats / tasks / system
system/core/           pipeline、extractor、ofd/pdf 解析、verify、risk、dedup、local_ocr
system/database/       connection（models/queries/writes/webhooks/locks Mixin）
system/services/       file / invoice / sync
system/components/     前端三件套（index.html / app.js / styles.css）
system/assets/vendor/  本地化第三方资源（tailwind / echarts / font-awesome）
system/mcp_server.py   本地 MCP Server（只读工具）
```

## 运行与验证（本项目**需要**起服务）

```bash
pip install -r system/requirements.txt
python api_server.py           # 默认 http://127.0.0.1:5000
```

- 冒烟：`/api/dashboard`、`/api/invoices`、`/api/stats/summary`、`/api/system/status`
- 测试：`python -m pytest system/tests/test_api.py -v`（会写 `system/data` 下的真实库，跑前先备份）
- 破坏性脚本：`system/tests/manual_stress.py --force`（默认拒绝执行）

## 编码约定

- Python 文件按职责拆分，单文件尽量 ≤ 350 行；超长文件已在 `system/tech_debt.md` 登记
- 数据库访问统一用 `with db_manager.connection() as conn`，不要手写 `close()`
- 查询返回 dict（不要返回元组靠下标取列）
- 失败必须有落点：要么重试、要么落盘到失败目录，**不允许静默丢弃**
- 外部能力（OCR/验真/推送）必须在未配置时降级，而不是抛错
- 改前端后要真开浏览器看一遍（本地资源已离线化，无需联网）

## 不要做的事

- 不要把 `host` 改回 `0.0.0.0`（默认仅本机；容器用 `INVOICE_HOST` 覆盖）
- 不要在业务代码里直接 `open(csv, 'w')` 覆盖台账（用 `export_to_csv` 的原子写）
- 不要给发票号加"软唯一"逻辑（已有部分唯一索引）
- 不要在测试里直接操作真实业务目录
- 不要提交 `.env`、`system/data`、归档目录
