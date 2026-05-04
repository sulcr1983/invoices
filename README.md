# 天颐 · 发票智能处理系统

自动识别、归档、推送增值税发票的轻量 Web 工具。

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
python api_server.py
```

访问 http://localhost:5000

## Docker 部署

```bash
docker build -t invoice-system .
docker run -d -p 5000:5000 -v ./待识别发票:/app/待识别发票 invoice-system
```

## 目录结构

```
├── api_server.py          # 根入口
├── 🚀 一键启动.bat         # Windows 启动脚本
├── Dockerfile             # 容器化部署
├── .env.example           # 环境变量模板
└── system/                # 核心黑盒（禁止污染根目录）
    ├── api_server.py      # Flask 应用工厂
    ├── config.py          # 全局配置（pathlib）
    ├── main.py            # CLI 入口
    ├── routes/            # Blueprint 路由模块
    ├── core/              # OCR/解析/流水线
    ├── database/          # SQLite 读写层
    ├── services/          # 文件/发票/同步服务
    ├── components/        # 前端 HTML/CSS/JS
    └── tests/             # 测试用例
```

## 功能

- PDF/图片发票 OCR 识别（百度增值税发票 OCR + pdfplumber 兜底）
- MD5 文件去重 + 发票号码去重，重复记录审计留存
- 自动归档（按年/月目录组织）、失败重试、企微 Webhook 推送
- 金额统计面板、销售方 TOP10、月度趋势图
- 专票 360 天抵扣期限预警
- 多维筛选（关键词/日期/金额/发票类型/推送状态）
- 异步处理（不阻塞 Web 界面）

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| BAIDU_API_KEY | 百度 OCR API Key | 空（跳过 OCR） |
| BAIDU_SECRET_KEY | 百度 OCR Secret Key | 空 |
| WECOM_WEBHOOK_URL | 企微 Webhook 地址 | 空（跳过推送） |
| LOG_LEVEL | 日志级别 | INFO |

## 测试

```bash
python system/tests/test_cases.py
```
