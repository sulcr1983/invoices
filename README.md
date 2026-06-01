<p align="center">
  <img src="https://img.shields.io/badge/版本-v10.2-4F46E5?style=for-the-badge&logo=github" alt="版本" />
  <img src="https://img.shields.io/badge/许可证-MIT-10B981?style=for-the-badge&logo=opensourceinitiative" alt="许可证" />
  <img src="https://img.shields.io/badge/AI-百度智能云-244080?style=for-the-badge&logo=baidu" alt="AI引擎" />
  <img src="https://img.shields.io/badge/平台-Windows-0078D4?style=for-the-badge&logo=windows" alt="平台" />
</p>

<h1 align="center">⚡ SuperSu 发票自动识别验真推送系统</h1>

<p align="center">
  <strong>免费 · AI驱动 · 开箱即用</strong>
</p>

<p align="center">
  拖进去，3秒出结果。从"手动搬砖"变成"一键搞定"。
</p>

<p align="center">
  <img src="https://img.shields.io/badge/🤖-AI智能识别-4F46E5?style=for-the-badge" />
  <img src="https://img.shields.io/badge/🔍-一键验真-DC2626?style=for-the-badge" />
  <img src="https://img.shields.io/badge/📊-统计分析-7C3AED?style=for-the-badge" />
  <img src="https://img.shields.io/badge/💬-企微推送-07C160?style=for-the-badge" />
</p>

---

## 💡 一句话介绍

> 一款**完全免费**、**AI驱动**、**无需安装**的发票智能处理工具 —— 基于百度智能云OCR高精度识别，支持批量验真、自动去重、一键统计，还能推送到企业微信。

---

## 🤖 AI 核心能力（区别于普通OCR工具）

### 🔥 百度智能云 OCR 高精度识别

SuperSu 集成百度智能云 OCR 引擎，与普通开源OCR工具有着本质区别：

| 能力 | 普通开源OCR | SuperSu + 百度智能云 |
|:---|:---|:---|
| 🎯 **识别准确率** | ~70-80%（印刷体） | **~98%+**（发票专用优化） |
| 📄 **OFD格式** | ❌ 不支持 | ✅ XML直接解析，秒级完成 |
| 🖼️ **图片发票** | ❌ 不支持 | ✅ JPG/PNG高精度识别 |
| 🔢 **字段提取** | 纯文本，需正则匹配 | **智能结构化提取**，直接拿到发票号码/金额/税号等16个字段 |
| 📐 **倾斜/模糊** | ❌ 识别率大幅下降 | ✅ 自动纠正，高容错率 |
| 🌙 **复杂背景** | ❌ 容易误识别 | ✅ 智能去噪，精准提取 |

> 💡 **配置方式：** 在百度智能云平台免费申请 OCR 应用（每月有一定免费额度），获取 API Key 填入 `.env` 即可启用。

### ✅ 百度智能云发票验真

- 一键调用国家税务总局发票查验接口，**实时验证发票真伪**
- 批量验真：勾选多张发票一键批量查验
- 费用透明：每次验真 ¥0.25，前端实时显示预估费用

> ⚠️ 验真功能需要配置百度智能云 API Key，按次计费。

---

## 🎯 解决什么痛点

| 😫 传统方式 | ✅ SuperSu 方案 |
|:---|:---|
| 逐张打开PDF手动抄录信息，一张2分钟 | 批量拖入，AI自动识别，30秒全部入库 |
| 查重靠肉眼在Excel里搜索发票号 | 文件MD5 + 发票号码双重自动去重 |
| 归档靠手动建文件夹、复制文件 | 按年/月自动分类归档 |
| 统计靠Excel公式，容易出错 | 可视化图表，实时统计，一键导出 |
| 验真要登录国家税务总局网站手动查 | 批量勾选一键验真，自动回传结果 |
| 推送靠手动发群消息、填表格 | 识别成功自动推送企微智能表格 |
| 风险检测靠人工翻找 | 大额发票、疑似拆票自动标记预警 |

---

## 🏆 同类方案对比

| 功能特性 | ⚡ SuperSu<br/><sub>（本系统）</sub> | 💰 商业SaaS平台A | 💰 商业SaaS平台B | 🧩 开源OCR工具 |
|:---|:---:|:---:|:---:|:---:|
| 💵 **价格** | 🟢 **完全免费** | ¥2999+/年 | ¥1999+/年 | 免费 |
| 🤖 **AI识别引擎** | ✅ 百度智能云OCR | ✅ 自研AI | 基础OCR | ❌ 无AI |
| 🎯 **识别准确率** | **~98%+** | ~95%+ | ~85% | ~70% |
| 📄 **格式支持** | PDF/OFD/JPG/PNG | PDF/JPG/PNG | PDF/JPG | PDF/图片 |
| 🔍 **智能去重** | ✅ 双重去重+审计 | ✅ | ✅ | ❌ |
| ✅ **批量验真** | ✅ 一键批量 | ✅ | ✅ | ❌ |
| 📊 **统计分析** | ✅ 图表+导出 | ✅ 付费版 | 基础 | ❌ |
| 💬 **企微推送** | ✅ 智能表格 | ✅ | ❌ | ❌ |
| 🚀 **部署方式** | 一键启动免安装 | 注册即用 | 注册即用 | 需搭建环境 |
| 🔒 **数据安全** | 🟢 完全本地 | ☁️ 云端 | ☁️ 云端 | 本地 |
| 📱 **多端适配** | ✅ 电脑/平板/手机 | ✅ | ✅ | ❌ |
| 🔧 **可定制** | ✅ 开源可改 | ❌ | ❌ | ✅ |

---

## ⚡ 核心功能

### 🤖 AI 智能识别

- **🎯 百度智能云OCR** — 发票专用高精度识别，准确率高达98%+
- **📄 OFD直解** — 直接解析OFD的XML结构，秒级完成，最快最准
- **📄 PDF多引擎** — 智能选择OCR或文本提取，自动适配最优方案
- **🖼️ 图片识别** — JPG/PNG发票图片也能高精度识别

### ✅ 发票验真

- **🔍 单张验真** — 发票详情页面一键调用百度验真接口
- **📦 批量验真** — 勾选多张发票批量验真，费用实时预估
- **🏷️ 批量认证** — 专票已认证/未认证状态批量管理
- **💰 费用透明** — 每次验真 ¥0.25，前端实时显示预估费用

### 🔄 智能去重

- **文件MD5校验** — 同一文件重复提交自动拦截
- **发票号码校验** — 不同文件但发票号码相同，同样拦截
- **审计记录留存** — 每次重复拦截都有完整日志记录

### 🚨 风险预警

- **大额预警** — 单张发票超过 ¥10,000 自动标记
- **拆票检测** — 同销售方同日期疑似拆分发票自动标记
- **到期预警** — 专票360天抵扣期限，已过期/即将到期自动提醒

### 📈 统计分析

- **💰 总览卡片** — 发票总额 / 总税额 / 发票数量 / 本月新增
- **📊 月度趋势** — 价税堆叠柱状图，12个月走势一目了然
- **🏆 销售方排名** — TOP10销售方排行，点击可跳转筛选
- **🥧 类型占比** — 普票/专票/电子发票/其他饼图分布
- **📋 进项税追踪** — 专票已认证/未认证分类汇总
- **📅 自定义范围** — 任意日期范围筛选统计

### 💬 企微推送

- **📤 自动推送** — 识别成功后自动推送至企业微信智能表格
- **🔗 Webhook** — 支持多平台Webhook配置与连接测试
- **📋 字段映射** — 16个发票字段自动映射到企微表格字段

### 🏷️ 费用归属

- **📁 部门标签** — 按部门/项目/费用类型分类管理
- **📦 批量设置** — 勾选多张发票批量设置归属
- **📊 费用统计** — 按归属维度统计金额分布

### 📊 数据管理

- **🗂️ 发票台账** — 支持关键词搜索、高级筛选、表头排序、分页浏览
- **🔍 多维筛选** — 日期范围 / 发票类型 / 推送状态 / 验真状态 / 风险等级组合筛选
- **📋 详情编辑** — 发票详情弹窗，可编辑备注、修改费用归属
- **📥 CSV导出** — 一键导出台账，Excel直接打开

---

## 🚀 快速开始（3步搞定）

### 方式一：Python环境（推荐）

```bash
# 1️⃣ 安装依赖
pip install -r system/requirements.txt

# 2️⃣ 启动系统
双击 🚀 一键启动.bat
# 或 python system/api_server.py

# 3️⃣ 浏览器访问
http://localhost:5000
```

### 方式二：绿色便携版（无需安装Python）

```bash
# 1️⃣ 运行打包脚本
python build_portable.py

# 2️⃣ 进入生成目录
cd dist/portable

# 3️⃣ 双击启动
双击 SuperSu发票系统.bat
```

> 💡 **没有Python环境？** 绿色版自带Python运行时，解压即用，发给同事零门槛使用。

### 方式三：Docker部署

```bash
docker build -t supersu-invoice .
docker run -d -p 5000:5000 \
  -v ./待识别发票:/app/待识别发票 \
  -v ./已归档发票:/app/已归档发票 \
  supersu-invoice
```

---

## 🔧 配置说明

### 基础使用（零配置）

> **不需要任何配置！** 直接启动即可使用 PDF 文本提取模式。

### 增强配置（推荐启用AI能力）

创建 `.env` 文件并填入以下配置：

```bash
# 百度智能云 OCR（推荐，识别准确率98%+）
BAIDU_APP_ID=你的APP_ID
BAIDU_API_KEY=你的API_KEY
BAIDU_SECRET_KEY=你的SECRET_KEY

# 企业微信智能表格推送（可选）
WECOM_WEBHOOK_URL=你的Webhook地址
WECOM_SCHEMA={"fdlY8t":"发票号码",...}
```

| 配置项 | 说明 | 默认值 |
|:---|:---|:---|
| `BAIDU_APP_ID` | 百度智能云应用ID | 空（使用文本提取） |
| `BAIDU_API_KEY` | 百度OCR API Key | 空 |
| `BAIDU_SECRET_KEY` | 百度OCR Secret Key | 空 |
| `WECOM_WEBHOOK_URL` | 企微Webhook地址 | 空（跳过推送） |
| `VERIFY_ENABLED` | 是否启用验真 | `true` |
| `VERIFY_COST_PER_CALL` | 验真费用(元/次) | `0.25` |

> 📝 百度智能云OCR应用申请：[https://console.bce.baidu.com/ai/#/ai/ocr/overview/index](https://console.bce.baidu.com/ai/#/ai/ocr/overview/index)

---

## 📊 性能数据

| 指标 | 数值 |
|:---|:---|
| 📄 OFD XML解析 | ~0.3秒/份 |
| 📄 PDF文本解析 | ~0.5秒/份 |
| 🤖 AI OCR识别 | ~1-3秒/份 |
| 📋 100张发票识别 | ~30-60秒 |
| 💻 内存占用 | ~80MB |

---

## 🆕 更新记录

<details>
<summary><strong>v10.2 (2026-06-01) — 品牌升级 + 安全修复</strong></summary>

- 🏷️ **品牌升级**: 系统名称更改为 "SuperSu 发票自动识别验真推送系统"
- 🔧 **P0 端口冲突修复**: 启动时自动检测并释放占用端口
- 🔧 **P1 启动脚本优化**: 增加端口检测和旧进程清理
- 🔧 **P2 API路由修复**: `/api/*` 路径正确返回JSON 404
- 🔧 **P3 字段补全**: Dashboard补充 `archived_cnt` 字段
- 🔧 **P4 弃用修复**: `pipeline.py` 改用 `importlib.metadata`
- 🔧 **P5 请求优化**: 前端统计API加入AbortController防抖
- 📦 **打包优化**: Python 3.11.9 + 体积清理优化
- 🔒 **安全**: 移除测试产物、数据库、日志等敏感文件
</details>

<details>
<summary><strong>v10.1 (2026-05-15) — 关键修复</strong></summary>

- 修复流水线崩溃 (`cannot access local variable`)
- 文件锁死锁自动释放 (30分钟过期清理)
- 数据库连接泄漏修复
- ECharts内存泄漏修复
- 浮点比较容差优化
</details>

<details>
<summary><strong>v10.0 (2026-05-07) — 大版本升级</strong></summary>

- 仪表盘重构、发票列表升级、批量验真增强
- 统计页增强、详情弹窗优化、销售方可点击
- 风险表格化、代码清理
</details>

---

## 🤝 参与贡献

欢迎提交 Issue 和 Pull Request！

- 🐛 报告Bug → [Issues](https://github.com/sulcr1983/invoices/issues)
- 💡 功能建议 → [Issues](https://github.com/sulcr1983/invoices/issues)
- 🔧 提交代码 → [Pull Requests](https://github.com/sulcr1983/invoices/pulls)

---

## 📄 许可证

[MIT License](LICENSE) · 免费使用 · 可商用 · 可修改

---

<p align="center">
  <strong>⚡ SuperSu — 让发票处理不再是负担</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Made%20with-❤️-red?style=flat-square" />
  <img src="https://img.shields.io/badge/Free-Forever-10B981?style=flat-square" />
  <img src="https://img.shields.io/badge/AI%20Powered-True-4F46E5?style=flat-square" />
</p>
