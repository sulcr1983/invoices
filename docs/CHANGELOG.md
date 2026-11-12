# 变更记录

格式参考 Keep a Changelog；版本号以 `system/__init__.py:__version__` 为准。

## [11.1.0] - 2026-11-12

本轮以「安全 + 可诊断 + 诚实」为主，逐条对应 `docs/AUDIT-2026-11-12.md` 的发现。

### 安全
- 上传接口：文件名清洗（剥离路径分隔符/危险字符）+ 后缀白名单，修复目录穿越
- 默认监听改为 `127.0.0.1`（容器用 `INVOICE_HOST` 覆盖）
- CORS 收紧为仅本机来源
- 新增 `.dockerignore`，镜像不再夹带 `.env`、数据库与归档原件

### 数据可靠性
- 台账 CSV 改为「临时文件 + `os.replace`」原子写
- 启动时自动做 SQLite 热备份（`invoices.db.backup`）
- 发票号加**部分唯一索引**（排除空号），杜绝同号重复入库
- 归档重名自动 `_1` 递增，且归档后校验原件已离开处理中目录
- 启动时恢复 `X-处理中临时` 遗留文件；失败目录重投上限 3 次
- 数据库启用 WAL 与 `foreign_keys`

### 可诊断
- Web 模式接入 `setup_logging()`（此前日志从未落盘）
- UI 日志 Handler 挂到 `system` 父级，能收到 OCR/DB 错误
- `/api/system/logs` 文件缺失时返回 `warning`，不再静默空数组
- `api_error` 不再误用 `logger.exception`（消除 `NoneType: None` 噪声）
- 文件锁增加 30 分钟 TTL 清理

### 功能修正
- 验真：`total_amount` 改用价税合计；类型无法判断时不传 `invoice_type`（原实现 11/11 失败）
- 验真失败不再计入费用估算
- 批量验真前端修正二次解包（结果面板此前恒为空）
- 分页参数校验：`limit=0` / `page=abc` 返回 400，`limit` 上限 200
- 快捷筛选与手填日期二选一，避免参数重复导致筛选失效
- 首页"已归档金额"去掉重复的 ¥ 符号
- 上传结果提示补充"跳过/拒绝"数量
- 客户端 CSV 导出改为标准引号转义（备注含逗号/换行不再错行）
- `saveAll` 半成功时给出精确提示，不再统一报"保存成功"
- 状态预警改用后端聚合计数，不再拉 1000 条在浏览器里数
- 原件定位改为精确后缀匹配 + 按年月限定，避免子串误命中与全盘 rglob
- 抵扣期限用 `date` 相减，当天到期不再误判"已过期"
- 统计接口改用连接上下文，修复异常路径连接泄漏
- 风险计数与风险列表统一日期口径
- 进项税季度统计补上界

### 新增能力
- **本地 OCR 兜底**：`core/local_ocr.py`（RapidOCR / ONNXRuntime，离线、按次不收费）
- **模糊去重**：`core/dedup.py`（RapidFuzz，同号不同 MD5 也能拦）
- **OFD 兜底**：easyofd 转 PDF 后复用文本/OCR 通道
- **本地 MCP Server**：`system/mcp_server.py`，5 个只读工具，零第三方依赖
- **前端离线化**：tailwind / echarts / font-awesome 落到 `system/assets/vendor/`

### 工程
- `test_cases.py` → `manual_stress_test.py`，加 `--force` 护栏，不再被 pytest 收集
- 新增 `INVOICE_DB_PATH` 环境变量，支持测试隔离
- 新增文档：`docs/TESTING.md`、`DEPLOYMENT.md`、`BACKUP.md`、`API.md`、`CHANGELOG.md`
- 重写 `CLAUDE.md` 为项目真实说明；`tech_debt.md` 降级为待办清单
- 11 份未填模板文档归档到 `.backup/2026-11-12/templates/`

## [11.0.0] - 2026-05-13
- 绿色便携打包（≈38MB）、移除 pandas/aiohttp/openpyxl、`INVOICE_PROJECT_ROOT` 支持

## [10.0.0] - 2026-05-07
- 仪表盘重构、快捷筛选与表头排序、批量验真弹窗、自定义统计周期、风险表格化

## [9.5.0] - 2026-05-06
- Tab hover 修复、详情弹窗「查看原件」恢复

## [9.4.0] / [9.3.0]
- 见 git 历史（此前 README 未记录，本次补齐版本号来源）
