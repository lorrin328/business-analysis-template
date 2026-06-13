# DATA_DICTIONARY

## 容器运行数据

| 数据项 | 路径/变量 | 说明 |
|---|---|---|
| SQLite 数据库 | `BUSINESS_ANALYSIS_DB` | 默认 `/data/business_data.db`，由 Docker volume 持久化。 |
| 应用日志 | `/app/backend/logs` | 由 Docker volume 持久化。 |
| 上传文件限制 | `MAX_UPLOAD_SIZE_MB` | Compose 默认 `100`。 |

## 业务数据

业务表、字段、指标口径沿用现有 `backend/db`、`backend/metrics`、`backend/etl` 实现。本次仅新增容器运行形态，未修改业务字段、接口或指标公式。
