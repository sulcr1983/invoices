# 测试说明

## 一句话

**`test_api.py` 会写真实数据库；`manual_stress.py` 会删真实发票文件。** 跑之前先读这一页。

## 两个测试文件

| 文件 | 类型 | 是否破坏性 | 怎么跑 |
|:--|:--|:--|:--|
| `system/tests/test_api.py` | pytest 用例（100 项） | 会写 `system/data/invoices.db` | 建议先用临时库（见下） |
| `system/tests/manual_stress.py` | 手工压测脚本 | **会删除/移动真实发票** | 必须 `--force`，且只在副本环境跑 |

> 历史上有第三个文件 `test_cases.py`，因为文件名匹配 `test_*.py`，`pytest` 会收集它并在 import 时清空业务目录。
> 已改名为 `manual_stress.py`，并加了 `--force` 护栏。

## 推荐：用临时库跑回归（不碰真实数据）

```bash
# 1. 造一份隔离环境
export ISOLATE=/tmp/supersu_test
mkdir -p "$ISOLATE/project"
cp -r system/data "$ISOLATE/project_data_tmp" 2>/dev/null || true
cp system/data/invoices.db "$ISOLATE/invoices.db"
cp 发票台账.csv "$ISOLATE/project/发票台账.csv"

# 2. 指向临时库与临时项目目录（Windows 用对应路径）
export INVOICE_DB_PATH="$ISOLATE/invoices.db"
export INVOICE_PROJECT_ROOT="$ISOLATE/project"

# 3. 跑
python -m pytest system/tests/test_api.py -v
```

`INVOICE_DB_PATH` 与 `INVOICE_PROJECT_ROOT` 是专门为隔离加的两个环境变量（`system/config.py`）。

## 冒烟测试（最快的一次自检）

```bash
python api_server.py          # 另开一个窗口
curl http://127.0.0.1:5000/api/dashboard
curl http://127.0.0.1:5000/api/invoices
curl http://127.0.0.1:5000/api/stats/summary
curl http://127.0.0.1:5000/api/system/status
```

预期：全部返回 `{"status":"success", ...}`；`/api/invoices?limit=0` 应返回 **400**（参数校验），不是 500。

## 本轮修复对应的回归点

| 修复 | 验证方式 |
|:--|:--|
| 上传文件名清洗 | 上传 `../../../evil.bat` → 出现在 `rejected`，磁盘无文件 |
| 分页参数 | `limit=0` / `page=abc` → 400 |
| 推送假成功 | 无 webhook 时新记录 `push_status` = `skipped` |
| 日志初始化 | `system/logs/app.log` 存在且 `/api/system/logs` 非空 |
| 台账原子写 | 导出后无 `.tmp` 残留；中途中断不产生半截文件 |
| 发票号唯一 | 重复号码插入被拒，写入 `duplicate_records` |
| 归档重名 | 同名归档生成 `_1` 后缀，处理中目录不残留 |
| 验真字段 | `verify.py` 使用 `total_amount`；类型未知时不传 `invoice_type` |
| 本地 OCR | 断网 + 无百度 Key，扫描件仍能出文本 |
| 模糊去重 | 同号不同 MD5 → `duplicate_similar` |
| MCP | `initialize` / `tools/list` / `tools/call` 三次握手正常 |

## 注意

- 跑完 `manual_stress.py` 后，`待识别发票/` 等目录会被清空，**请先确认里面没有真实发票**。
- 备份方式见 [BACKUP.md](BACKUP.md)。
