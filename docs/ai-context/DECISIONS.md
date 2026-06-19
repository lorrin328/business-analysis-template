# 决策记录

## 2026-06-19 看板全局截至日期口径

### 决策

经营分析主看板采用全局 `asOf` 截至日期控制主要业务模块的数据口径。前端以右上角“数据截止”下拉作为唯一交互入口，后端通过 `asOf=YYYY-MM-DD` 参数统一截断 KPI、平台趋势、产品结构、机构维度和交期结构。

### 原因

- 经代与转型业务存在导入日期和自然日期不一致的情况，未满月同比必须按同日口径比较。
- 右上角统一选择能避免 KPI、趋势、产品、机构等模块各自采用不同截止时间，降低经营复核误差。
- 现有日级聚合表已能支撑 KPI 和平台趋势按日截断，产品明细也可从原始明细按日期截断。

### 影响

- 导入数据最新日期与系统日期相差 2 天及以上时，页面提示“请注意数据口径”。
- 交期结构当前来源为月级聚合表，只能随 `asOf` 截至月份截断；若未来要求同月内按天精确截断，需要改为从原始明细或新增日级交期聚合表计算。

## 2026-06-13 容器镜像发布方式

- 决策：使用 GitHub Actions 构建镜像并推送到 GitHub Container Registry。
- 镜像名：`ghcr.io/lorrin328/business-analysis-template`。
- 原因：镜像二进制文件不适合直接提交到 Git 仓库；GHCR 支持 `latest`、分支、tag、sha 多维度版本管理，后续服务器可直接 `docker pull`。
- 约束：镜像不内置业务数据和真实密钥，SQLite 数据库、日志通过 volume 持久化。

## 2026-06-13 本地开发环境基线

### 决策

Windows 本地开发环境采用 Python 3.12、Git for Windows、uv 作为基础工具链；项目测试依赖继续保留在 `requirements.txt` 和 `backend/requirements.txt`，脚本显式安装或引用这两个 requirements 文件。

### 原因

- 项目声明 Python 3.10+，Python 3.12 可兼容当前测试集。
- `pyproject.toml` 当前未集中声明运行依赖，直接依赖 requirements 文件更贴合现状。
- `scripts/preflight.ps1` 是 Windows 上线前检查入口，必须能在新环境中自举测试依赖。

### 影响

- Windows 预检不再依赖预先手工安装 pytest/FastAPI/pandas 等包。
- Bash 测试脚本不再遗漏后端依赖。
