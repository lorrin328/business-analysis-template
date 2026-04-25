# 经营分析 - 产品结构测算

保险经营分析单页看板。前端 ECharts 5.5 + sql.js (SQLite-WASM)，浏览器内跑 SQL 完成所有筛选与聚合。

## 特性

- **日级精度**：月/季视图主图保持累计折线形态，hover 任意月/季弹出当期日累计明细 sparkline
- **纯静态部署**：双击 HTML 用本地 HTTP 服务即可，不需要后端
- **任意维度筛选**：10 个产品维度 × 3 个保费口径，毫秒级响应
- **多年同比**：支持 2024 / 2025 / 2026 任意年份的累计对比与 YoY 增速

## 数据准备

数据库由本地构建，**不入库**（见 `.gitignore`）。

```bash
# 1. 创建虚拟环境并安装依赖
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. 把日明细 Excel 放到项目目录，运行构建
python build_db.py --input "你的日明细文件.xlsx" --output data.db --force
```

源文件需要包含的列（中文）：

- 时间：`日期`（或 `投保日期`/`签单日期`）、`年`、`月`、`季`、`月标签`
- 维度：`销售机构名称`、`业务模式`、`是否在运营项目`、`分红产品`、`创新or传统`、`长短险`、`是否商保年金产品`、`缴费年限`、`保障年限`、`产品设计分类`
- 指标：`期交保费`、`年化规保`、`折算保费`（单位为元）

构建完成会打印行数、按年分布、负数行数、各指标合计，便于与原表对账。

## 本地启动

`sql.js` 的 wasm 不能在 `file://` 协议下加载，需要起一个静态 HTTP 服务：

```bash
python -m http.server 8000
```

浏览器打开 <http://localhost:8000/经营分析模板.html>。

## 数据更新流程

1. 拿到新一期的日明细 Excel
2. `python build_db.py --input 新文件.xlsx --force`
3. 浏览器刷新页面（无需重启服务）

## 文件结构

```
business-analysis-template/
├── README.md                 # 本文件
├── build_db.py               # Excel/CSV → SQLite 构建脚本
├── requirements.txt          # pandas、openpyxl
├── 经营分析模板.html          # 单页应用
├── data.db                   # 构建产物（本地）
└── .gitignore
```

## 技术栈

- ECharts 5.5（CDN）
- sql.js 1.10.3（CDN，含 WASM）
- pandas + openpyxl（仅构建期）

## 注意事项

- `data.db` 与原始 Excel 含敏感业务数据，已在 `.gitignore` 中屏蔽
- 同比基准年硬编码为 `2024`（HTML 顶部 `BASE_YEAR` 常量），如需切换集中改一处
- 浮点精度：金额按"分"以 INTEGER 入库，避免 IEEE754 尾噪
- 撤单/退保产生的负数严格保留（约 6% 行）
