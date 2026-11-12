# 技术债务清单

> 更新时间：2026-11-12 | 对应版本：v11.1
> 本文件已从「历史归档（曾声称全部已处理）」降级为**待办清单**，只记录当前真实状态。
> 检视依据：`docs/AUDIT-2026-11-12.md`（含实测证据）。

## 已关闭（本轮修复，有代码/测试佐证）

| 项 | 处理方式 |
|:--|:--|
| 上传文件名未清洗（路径穿越） | `routes/tasks.py` 新增 `_safe_upload_name`，剥路径 + 后缀白名单 |
| 测试脚本被 pytest 收集会删真实文件 | `test_cases.py` 改名 `manual_stress.py`，且必须 `--force` 才执行 |
| 无 webhook 时伪造成推送成功 | 新增 `update_push_skipped`，状态记 `skipped` |
| Web 模式日志从未初始化 | `create_app()` 首行调用 `setup_logging()` |
| 台账 CSV 非原子写 | 临时文件 + `os.replace()` 原子替换 |
| 数据库无备份 | 启动时 `sqlite3.backup()` 生成 `invoices.db.backup` |
| 发票号无唯一约束 | 部分唯一索引（排除空号） |
| 前端日志面板重复渲染 | 后端 `seq` 增量拉取 |
| 验真参数错（11/11 失败） | 改用价税合计；类型无法判断时不传 `invoice_type` |
| 批量验真结果恒空 | 修正 `apiRequest` 二次解包 |
| `limit=0` → 500 | 分页参数校验，非法返 400 |
| 归档重名导致文件滞留 | 重名走 `_1` 递增 + 归档后校验原件已离开 |
| 处理中目录无恢复 | 启动时 `recover_processing_dir()` |
| 失败目录无限重投 | 重投上限 `RETRY_MAX_ATTEMPTS`（默认 3） |
| 统计接口连接泄漏 | 改用 `with db_manager.connection()` |
| 原件定位子串误匹配 | 改为 `stem.endswith('_'+num)` + 按年月限定 |
| 前端依赖 4 个 CDN | tailwind / echarts / font-awesome 已本地化 |
| Docker 会把 .env 与真实数据打进镜像 | 新增 `.dockerignore`，Dockerfile 改为按需 COPY |

## 未关闭（已知，待排期）

| 优先级 | 项 | 原因 / 下一步 |
|:--|:--|:--|
| P2 | `core/ofd_parser.py` 683 行，含重复的购销方提取与税率归一化 | 建议拆 `ofd_xml.py` / `ofd_text.py`，抽 `normalize_tax_rate()`；改动面大，需 OFD 样本回归 |
| P2 | `components/app.js` 单文件 1900+ 行 | 建议按 dashboard/invoices/stats 拆模块，需前端构建链 |
| P2 | 仪表盘/统计 SQL 仍散在路由层 | 已下沉 `get_status_counts()` / `get_monthly_trend()`，其余可继续下沉 |
| P2 | `invoices.py` 与 `system.py` 各有一套"看原件"实现 | 已统一为精确匹配；建议再抽 `resolve_original()` 单一入口 |
| P2 | `deduction_status` 字段被复用作"认证状态/到期状态" | 语义过载，需新增独立字段并迁移 |
| P2 | `certification_status` 与 DB `deduction_status` 命名不一致 | 前端契约已固定，改名需同步前端 |
| P3 | `main.py` CLI 无文档 | 已在 README 目录树标注，待补 `docs/CLI.md` |
| P3 | `BAIDU_APP_ID` / `ENABLE_ALERT` / `ALERT_WEBHOOK_URL` 读取后未使用 | 已在 `.env.example` 标注"预留"，可后续清理或接入 |
| P3 | `webhooks` 表 CRUD 无路由暴露 | 当前通过 `.env` 配置即可，管理后台按需再做 |

## 历史归档（v11.0 及更早）

- 猴补丁 → Mixin 继承：已完成（`database/` 五个 Mixin）
- `RECORD_COLUMNS` 三处重复 → `database/columns.py` 单一来源：已完成
- 旧表结构迁移（补 `id` 主键）：已完成（`models.py:_migrate_old_schema`）

> 注：旧版本此文件曾写"全部已处理 ✅ / 154 用例 0 失败"，与实测不符（`api_server.py` 仍有 `sys.path.insert`，
> 测试脚本会写真实库）。本次已删除该结论，改为按证据记录。
