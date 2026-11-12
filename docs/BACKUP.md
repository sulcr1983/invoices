# 备份与恢复

## 一句话

**别直接 `cp` 正在使用的 `invoices.db`** —— 用 SQLite 的 backup API，或者先停服务。
（WAL 模式下还有 `-wal`/`-shm` 两个附属文件，只拷主文件可能拿到不完整状态。）

## 自动备份（已内置）

每次启动应用时，会执行一次热备份：

```
system/data/invoices.db.backup
```

实现：`DBManager.backup_database()` → `sqlite3.Connection.backup()`，原子且一致。

> 只保留最近 1 份（覆盖写）。需要多份请用下面的手动方案。

## 手动备份（推荐每周一次）

```bash
# 1. 数据库热备份（不停服务）
python -c "import sqlite3; s=sqlite3.connect('system/data/invoices.db'); d=sqlite3.connect('backup_2026-11-12.db'); s.backup(d); d.close(); s.close()"

# 2. 台账 CSV（原子写保证完整性，直接复制即可）
cp 发票台账.csv backup_台账_2026-11-12.csv

# 3. 原件与留痕
tar -czf backup_归档_2026-11-12.tar.gz 已归档发票 重复发票记录 识别失败待处理
```

Windows PowerShell 等价：

```powershell
python -c "import sqlite3; s=sqlite3.connect('system/data/invoices.db'); d=sqlite3.connect('backup.db'); s.backup(d); d.close(); s.close()"
Copy-Item 发票台账.csv backup_台账.csv
Compress-Archive -Path 已归档发票,重复发票记录,识别失败待处理 -DestinationPath backup_归档.zip
```

## 恢复

```bash
# 1. 停服务（Ctrl+C 或结束 python 进程）

# 2. 还原数据库
cp backup_2026-11-12.db system/data/invoices.db
rm -f system/data/invoices.db-wal system/data/invoices.db-shm   # 清掉旧 WAL 残留

# 3. 还原台账与原件
cp backup_台账_2026-11-12.csv 发票台账.csv
tar -xzf backup_归档_2026-11-12.tar.gz

# 4. 启动并自检
python api_server.py
curl http://127.0.0.1:5000/api/system/status
```

## CSV 与 DB 不一致时以谁为准？

**以 DB 为准。** `发票台账.csv` 是从 DB 导出的视图：

```bash
# 重新导出一份即可
python -c "
import sys; sys.path.insert(0,'.')
from system.db_manager import DBManager
from system.config import DB_PATH, LEDGER_PATH
DBManager(DB_PATH).export_to_csv(LEDGER_PATH)
"
```

## 迁移到新机器

1. 拷走：`system/data/`、`发票台账.csv`、`已归档发票/`、`重复发票记录/`、`识别失败待处理/`、`.env`
2. 新机器装依赖：`pip install -r system/requirements.txt`
3. 启动：`python api_server.py`
4. 打开页面，核对首页「已归档」张数与金额

## 不建议的做法

| 做法 | 风险 |
|:--|:--|
| 服务运行时 `cp invoices.db` | 可能拷到写了一半的页 |
| 只备份 `invoices.csv` | 丢失验真/认证/归属等字段 |
| 备份后不验证 | 恢复时才发现文件是空的 —— 建议每次备份后跑一次 `PRAGMA integrity_check` |

```bash
python -c "import sqlite3; print(sqlite3.connect('backup_2026-11-12.db').execute('PRAGMA integrity_check').fetchone())"
# 期望输出: ('ok',)
```
