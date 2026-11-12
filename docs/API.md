# HTTP API

所有接口前缀 `/api`，返回统一结构：

```json
{ "status": "success", "data": { } }
{ "status": "error", "message": "中文提示" }
```

分页接口统一返回 `page / limit / total / pages`。参数非法返回 **400**（`limit` 必须在 1–200，`page` ≥ 1）。

## 仪表盘

| 方法 | 路径 | 说明 |
|:--|:--|:--|
| GET | `/api/dashboard` | 处理概览、状态预警计数（`status_counts`）、目录统计、近 6 月趋势、最近 10 条 |

## 发票

| 方法 | 路径 | 参数 | 说明 |
|:--|:--|:--|:--|
| GET | `/api/invoices` | `keyword, date_from, date_to, seller, amt_from, amt_to, invoice_type, tax_rate, push_status, verify_status, risk_flags, sort_field(date\|amount), sort_dir, page, limit` | 台账列表 |
| GET | `/api/invoices/duplicates` | `page, limit` | 重复记录 |
| GET | `/api/invoices/<invoice_num>` | — | 单张详情 |
| GET | `/api/invoices/<invoice_num>/original` | — | 原件（精确匹配 `_<号码>`） |
| PUT | `/api/invoices/<invoice_num>/remark` | `{"remark": "..."}` | 改备注 |
| PUT | `/api/invoices/<invoice_num>/attribution` | `{"department","project","expense_type"}` | 费用归属 |
| POST | `/api/invoices/<invoice_num>/verify` | — | 单张验真（已验过直接返回） |
| POST | `/api/invoices/batch-verify` | `{"invoice_nums": [...]}` | 批量验真（返回 results/success/failed/skipped/total_cost） |
| POST | `/api/invoices/batch-certify` | `{"invoice_nums": [...], "certification_date"}` | 批量标记已认证 |
| GET | `/api/sellers` | — | 销售方去重列表 |
| GET | `/api/export/invoices` | 同列表筛选参数 | 导出数据（前端生成 CSV） |
| GET | `/api/verify/config` | — | 验真开关 / 是否可用 / 单次费用 |

## 任务与日志

| 方法 | 路径 | 参数 | 说明 |
|:--|:--|:--|:--|
| GET | `/api/tasks/pending` | — | 待处理文件（只含 pdf/ofd/jpg/jpeg/png） |
| POST | `/api/upload` | `multipart: files` | 上传；文件名清洗 + 后缀白名单；返回 uploaded/skipped/rejected |
| POST | `/api/tasks/process` | — | 启动后台处理（并发保护，重复启动返 409） |
| GET | `/api/tasks/status` | — | `running / stats / error` |
| GET | `/api/logs` | `count` 或 `since`(seq) | 处理日志；带 `since` 时增量返回 |
| POST | `/api/logs/clear` | — | 清空日志 |
| POST | `/api/logs/add` | `{"message","level"}` | 前端补写日志 |

## 统计

| 方法 | 路径 | 参数 | 说明 |
|:--|:--|:--|:--|
| GET | `/api/stats/summary` | `date_from, date_to` | 张数/金额/税额/销售方数 + TOP5 + 月度 + 类型占比 |
| GET | `/api/stats/expense-distribution` | `date_from, date_to` | 部门/费用类型分布 + 异常发票（口径与计数一致） |
| GET | `/api/stats/input-tax-summary` | `period=month\|quarter\|year\|all, date_from, date_to` | 专票进项税（季度含上界） |

## 系统

| 方法 | 路径 | 说明 |
|:--|:--|:--|
| GET | `/api/system/logs` | 文件日志（`count`, `level`；文件不存在时返回 `warning` 字段） |
| GET | `/api/system/status` | 环境/数据库/目录三项自检 |
| POST | `/api/invoice/original` | `{"md5": "..."}` 定位归档原件 |
| GET | `/api/invoice/file/<file_md5>` | 直接返回原件流 |
| POST | `/api/open-dir` | `{"dir": "待识别发票"}`，白名单目录 |
| GET | `/` `/<path>` | 前端静态页（`components/`） |
| GET | `/assets/<path>` | 本地化第三方资源（`assets/vendor/`） |

## 说明

- 除 `GET /`、`/assets/*` 外，全部为 JSON 接口
- 无鉴权，默认仅监听 `127.0.0.1`
- 错误统一走 `api_error()`，技术异常映射为中文业务提示
