# 部署说明

三种部署方式，选一种即可。**共同点：数据必须持久化，否则重建即丢。**

## 数据持久化清单（三套部署通用）

| 路径 | 内容 | 丢了会怎样 |
|:--|:--|:--|
| `system/data/invoices.db` | 台账数据库（含验真/认证/费用归属） | 全部结构化数据丢失 |
| `发票台账.csv` | 可直接用 Excel 打开的台账 | 报表丢失（可从 DB 重新导出） |
| `已归档发票/年/月/` | 发票原件 | 原件不可恢复 |
| `重复发票记录/` | 重复拦截留痕 | 审计证据丢失 |
| `识别失败待处理/` | 失败文件 + 重试计数 | 失败件丢失 |
| `.env` | 百度 Key / 企微 Webhook | 需重新配置 |

## 一、本地直跑（推荐自用）

```bash
pip install -r system/requirements.txt
cp .env.example .env        # 可选
python api_server.py        # http://127.0.0.1:5000
```

- 默认只监听 `127.0.0.1`（不对外网开放）
- 改端口：`INVOICE_PORT=5050 python api_server.py`
- Windows 也可双击 `🚀 一键启动.bat`（注意：该脚本历史中文已损坏，会自动建乱码目录，建议用上面的命令）

## 二、Docker

```bash
docker build -t invoice-system .
docker run -d -p 5000:5000 \
  -v ./system/data:/app/system/data \
  -v ./已归档发票:/app/已归档发票 \
  -v ./重复发票记录:/app/重复发票记录 \
  -v ./识别失败待处理:/app/识别失败待处理 \
  -v ./待识别发票:/app/待识别发票 \
  -v ./发票台账.csv:/app/发票台账.csv \
  -e INVOICE_HOST=0.0.0.0 \
  invoice-system
```

- 容器内必须 `INVOICE_HOST=0.0.0.0` 才能被端口映射访问
- `.dockerignore` 已排除 `.env`、`system/data`、归档目录，镜像里不会夹带真实数据
- **只挂 `待识别发票` 是不够的**，台账/归档/CSV 会随容器删除一起消失

## 三、绿色便携包

```bash
python build_portable.py     # 输出 dist/portable/
```

- 目标机器无需 Python
- 数据落在便携目录内，整目录拷走即迁移
- 反病毒软件可能误报打包后的自解压程序，属常见现象

## 启动自检

```bash
curl http://127.0.0.1:5000/api/system/status
# {"data":{"environment":true,"database":true,"directories":true},"status":"success"}
```

启动时会自动做两件事：初始化日志（`system/logs/app.log`）、备份数据库（`system/data/invoices.db.backup`）。

## 端口与反向代理

生产/常驻建议放在 Nginx 后面并只监听本机：

```nginx
location / {
    proxy_pass http://127.0.0.1:5000;
    proxy_set_header Host $host;
}
```

> 本项目没有账号体系，**不要直接暴露到公网**。
