# 天颐 · 发票智能处理系统

> 每月几十张发票，手动录入又慢又容易出错？拖进去，3秒出结果。

## 它解决了什么痛苦

财务/行政人员每月要处理大量增值税发票：手动录入发票号码、金额、税号，费时费力还容易出错。查重靠肉眼，归档靠手动建文件夹，统计靠Excel——整个流程又慢又乱。

**天颐**让你把发票文件往里一拖，自动识别、自动去重、自动归档、自动统计，从"手动搬砖"变成"一键搞定"。

## 3个真实场景

**场景1：月底集中报销**
> 小王月底要报销20张发票。以前：逐张打开PDF抄信息到Excel，花1小时。现在：20个文件一起拖进去，点"开始处理"，30秒全部识别入库，台账自动生成。

**场景2：防止重复报销**
> 同一张发票被不同人提交了两次。以前：靠肉眼在Excel里搜发票号。现在：系统自动检测MD5和发票号码重复，重复发票直接拦截，还有审计记录。

**场景3：年底统计汇总**
> 老板要全年发票统计。以前：翻遍所有文件夹手动汇总。现在：打开统计面板，总金额、税额、销售方排名、月度趋势一目了然，还能导出CSV。

## 极简使用（3步搞定）

```
第1步：打开 → 浏览器访问 http://localhost:5000
第2步：拖入 → 把发票文件拖到上传区（支持 PDF、OFD、JPG、PNG）
第3步：点击 → 点"开始处理"，等几秒就完成
```

## 功能清单

| 功能 | 说明 |
|------|------|
| 多格式识别 | PDF、OFD、JPG、PNG 全支持，OFD直接解析XML（最快最准），PDF/图片走百度OCR |
| 智能去重 | 文件MD5 + 发票号码双重去重，重复记录留存审计 |
| 自动归档 | 按年/月目录自动归档，失败文件自动重试 |
| 批量验真 | 勾选多张发票一键调用百度验真接口，逐张返回结果并扣除费用（需配置API） |
| 批量认证 | 批量标记专票已认证状态，追踪进项税抵扣 |
| 异常检测 | 单张大额（>1万元）/疑似拆票自动标记，风险列表表格化展示 |
| 快捷筛选 | 发票列表支持全部/本月/近三月/未验真/高风险一键筛选 |
| 排序功能 | 按开票日期、价税合计点击排序，正序/倒序切换 |
| 费用归属 | 按部门/项目/费用类型标签化管理，支持批量设置 |
| 企微推送 | 识别成功自动推送企业微信智能表格Webhook |
| 统计分析 | 总额/税额/销售方TOP10/月度堆叠趋势/发票类型占比饼图 |
| 自定义统计 | 支持任意日期范围筛选统计，结果可导出CSV报表 |
| 进项税追踪 | 专票已认证/未认证分类汇总，按税率统计可抵扣税额 |
| 到期预警 | 专票360天抵扣期限自动预警（已过期/即将到期） |
| 多维筛选 | 关键词/日期/金额/发票类型/推送状态/验真状态组合筛选 |
| CSV导出 | 一键导出发票台账为Excel兼容的CSV文件 |
| 异步处理 | 后台线程处理，不阻塞界面操作 |
| 全设备适配 | 电脑、平板、手机均可正常使用 |

## 快速开始

```bash
# 1. 安装依赖
pip install -r system/requirements.txt

# 2. 配置环境变量（可选：百度OCR、企微Webhook）
cp .env.example .env
# 编辑 .env 填入 API Key

# 3. 启动
双击 🚀 一键启动.bat
# 或
python system/api_server.py
```

访问 http://localhost:5000

## Docker 部署

```bash
docker build -t invoice-system .
docker run -d -p 5000:5000 -v ./待识别发票:/app/待识别发票 invoice-system
```

## 目录结构

```
├── 🚀 一键启动.bat         # Windows 一键启动脚本
├── Dockerfile              # Docker 容器化部署
├── .env.example            # 环境变量模板
├── 待识别发票/              # ← 放入发票文件
├── 已归档发票/              # 处理成功的发票归档于此
├── 识别失败待处理/           # 识别失败的文件暂存
├── 重复发票记录/            # 重复发票文件暂存
└── system/                 # 核心代码
    ├── api_server.py       # Flask 应用工厂 + 入口
    ├── config.py           # 全局配置 + 环境变量
    ├── main.py             # CLI 入口（run/retry/check）
    ├── extractor.py         # 发票提取编排（OFD→OCR→文本回退）
    ├── webhook_manager.py  # Webhook 推送管理
    ├── db_manager.py       # 数据库管理器入口
    ├── routes/             # Flask Blueprint 路由层
    │   ├── dashboard.py    # 仪表盘 API
    │   ├── invoices.py    # 发票 CRUD + 验真 + 认证
    │   ├── stats.py        # 统计分析 API
    │   ├── tasks.py        # 文件上传 + 异步处理
    │   ├── system.py       # 系统状态 + Webhook + 前端服务
    │   └── shared.py       # 共享状态 + 日志 + 错误翻译
    ├── core/               # 核心引擎
    │   ├── pipeline.py     # 主流水线（扫描→识别→归档→推送）
    │   ├── baidu_ocr.py    # 百度 OCR API 集成
    │   ├── invoice_parser.py # 百度OCR结果映射
    │   ├── ofd_parser.py   # OFD 格式 XML 解析
    │   ├── text_invoice_parser.py # PDF文本正则回退解析
    │   ├── pdf_utils.py    # PDF转图片/提取文本
    │   ├── verify.py       # 发票验真（百度API + Mock）
    │   ├── risk_checker.py # 风险检测（大额/拆票）
    │   ├── data_utils.py   # MD5/金额/日期清洗
    │   └── webhook_payload.py # 企微Webhook负载构建
    ├── database/           # SQLite 数据访问层
    │   ├── connection.py   # 连接管理 + 事务
    │   ├── models.py        # 建表 + 迁移
    │   ├── queries.py       # 查询
    │   ├── writes.py        # 写入
    │   ├── webhooks.py      # Webhook CRUD
    │   ├── locks.py         # 文件锁（含过期清理）
    │   ├── columns.py       # 列定义
    │   └── ...              # 其他
    ├── services/            # 业务服务层
    │   ├── file_service.py  # 文件移动/归档/扫描
    │   ├── invoice_service.py # 发票处理编排
    │   └── sync_service.py  # 同步/补偿推送
    ├── components/          # 前端
    │   ├── index.html       # SPA 单页应用
    │   ├── app.js           # 业务逻辑
    │   └── styles.css       # 统一设计系统
    └── tests/               # 测试用例
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| BAIDU_API_KEY | 百度 OCR API Key | 空（跳过OCR，用文本提取兜底） |
| BAIDU_SECRET_KEY | 百度 OCR Secret Key | 空 |
| WECOM_WEBHOOK_URL | 企微智能表格 Webhook 地址 | 空（跳过推送） |
| WECOM_SCHEMA | 企微字段映射JSON | 空 |
| VERIFY_ENABLED | 是否启用验真 | true |
| LOG_LEVEL | 日志级别 | INFO |
| SQLITE_TIMEOUT | SQLite连接超时(秒) | 20 |
| REQUEST_TIMEOUT | HTTP请求超时(秒) | 10 |
| RETRY_MAX_ATTEMPTS | Webhook重试次数 | 3 |
| RETRY_DELAY_SECONDS | Webhook重试间隔(秒) | 2 |

## API 接口一览

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | /api/dashboard | 仪表盘数据 |
| GET | /api/invoices | 发票列表（支持筛选/分页/排序） |
| GET | /api/invoices/{num} | 发票详情 |
| PUT | /api/invoices/{num}/remark | 更新备注 |
| PUT | /api/invoices/{num}/attribution | 更新费用归属 |
| POST | /api/invoices/{num}/verify | 单张验真 |
| POST | /api/invoices/batch-verify | 批量验真 |
| POST | /api/invoices/batch-certify | 批量认证 |
| GET | /api/invoices/duplicates | 重复发票记录 |
| GET | /api/export/invoices | 导出发票数据 |
| GET | /api/sellers | 销售方列表 |
| GET | /api/verify/config | 验真配置 |
| GET | /api/stats/summary | 统计概要 |
| GET | /api/stats/expense-distribution | 费用分布+风险 |
| GET | /api/stats/input-tax-summary | 进项税汇总 |
| GET | /api/stats/invoice-counts | 发票状态计数（轻量） |
| GET | /api/tasks/pending | 待处理文件列表 |
| POST | /api/tasks/process | 启动处理流水线 |
| GET | /api/tasks/status | 流水线状态 |
| POST | /api/upload | 上传发票文件 |
| GET | /api/logs | 处理日志 |
| GET | /api/system/status | 系统状态检查 |
| POST | /api/open-dir | 打开目录（资源管理器） |
| GET | /api/webhook/config | Webhook配置 |
| POST | /api/webhook/test | 测试Webhook连接 |

## 处理流程

```
放入发票 → 待识别发票/ → 扫描文件 → MD5查重 → 移入处理中/
    ↓
OFD? → 解析XML → 成功?
    ↓否
百度OCR可用? → PDF转图片 → OCR识别 → 成功?
    ↓否
PDF文本提取 → 正则回退解析 → 校验
    ↓
写入数据库 → 风险检测 → Webhook推送 → 归档 → 导出台账
```

## 更新记录

### v10.1 (2026-05-15)

- **[关键修复] 处理流程无法运行**: 修复 `tasks.py` 中 logging import 顺序错误导致的 `cannot access local variable` 崩溃
- **[关键修复] 文件锁死锁**: 新增过期锁清理机制，崩溃后遗留的文件锁会在30分钟后自动释放
- **[修复] 流水线并发安全**: 添加线程锁保护 `_pipeline_result` 共享状态，防止并发触发
- **[修复] 数据库连接泄漏**: `dashboard.py`/`stats.py` 添加 `try/finally` 保护连接关闭
- **[修复] CSS设计令牌冲突**: 合并两套同名变量为一套，消除颜色/圆角/间距不一致
- **[修复] 金额双¥符号**: 修复 `formatMoney()` 已带¥前缀但调用方又手动添加的问题
- **[修复] 风险阈值不一致**: 统一后端阈值（1万元）与前端描述（原写10万元）
- **[修复] ECharts内存泄漏**: 切换统计页时先dispose旧实例再init新实例
- **[优化] 仪表盘性能**: 新增 `/api/stats/invoice-counts` 轻量级计数API，替代前端拉取1000条发票做客户端计数
- **[优化] 进程日志线程安全**: `process_logs` 改用 `deque(maxlen=100)` + `threading.Lock`
- **[优化] 浮点比较容差**: `verify_invoice_math` 使用 `abs(diff) < 0.01` 替代 `diff == 0`
- **[优化] 数据库索引**: `invoice_num` 改为UNIQUE索引，新增 `verify_status`/`deduction_status` 索引
- **[优化] 路径安全**: `/api/open-dir` 和静态文件路径添加遍历校验
- **[优化] 静态文件路径**: 使用绝对路径定位 components 目录，避免工作目录依赖

### v10.0 (2026-05-07)

- **仪表盘重构**: 分离"处理概览"和"状态预警"区块，月度趋势改为价税堆叠柱状图
- **发票列表升级**: 快捷筛选标签（全部/本月/近三月/未验真/高风险）、表头排序、风险行高亮
- **批量验真增强**: 新增批量验真确认/结果弹窗，费用预估，选中数量实时显示
- **统计页增强**: 自定义日期范围选择器、发票类型占比饼图(ECharts)、CSV报表导出
- **详情弹窗优化**: 新布局排版(meta网格+类型Badge)，认证状态栏，验真/原件按钮重新排列
- **销售方可点击**: 统计页销售方排名点击直接跳转发票列表并自动筛选
- **风险表格化**: 异常发票列表改为表格布局，点击行查看详情
- **代码清理**: 删除重复配置文件、死代码、重复常量定义，同步README

### v9.5 (2026-05-06)

- **Tab hover修复**: 覆盖Tailwind全局transition，移除hover特效
- **原件按钮恢复**: 发票详情验真按钮左侧恢复"查看原件"按钮

## 测试

```bash
# 运行 API 测试（99项）
python -m pytest system/tests/test_api.py -v
```
