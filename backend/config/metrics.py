"""指标定义与口径配置 — 前后端统一指标规范。

来源：docs/指标口径说明.md
所有核心指标公式统一放在 backend/metrics/，前端不得重复编写经营指标公式。
所有除法统一使用 safe_divide，自动处理 0、None、NaN、Infinity。
"""

METRICS = {
    "achievement_rate": {
        "name": "达成率",
        "unit": "%",
        "definition": "实绩 / 目标",
        "uncalculable_rule": "目标为空或为 0",
    },
    "yoy": {
        "name": "同比",
        "unit": "%",
        "definition": "本期 / 去年同期 - 1",
        "uncalculable_rule": "去年同期为 0 或缺失",
        "note": "去年同期指相对于当前统计日，上一年的同一日。例如，当前数据截至 2026-05-21，则去年同期为 2025-01-01 至 2025-05-21 的累计数据。",
        "granularity_limitations": [
            "期交保费：支持日级精度（使用日累计表）。",
            "人力指标（活动率、人均保费、人均产能）：仅月级精度（人力基表无日维度）。",
            "价值保费、长险期交、产品结构：仅月级精度（对应聚合表无日维度）。",
        ],
    },
    "mom": {
        "name": "环比",
        "unit": "%",
        "definition": "本期 / 上期 - 1",
        "uncalculable_rule": "上期为 0 或缺失",
    },
    "time_progress": {
        "name": "序时进度",
        "unit": "%",
        "definition": "已过时间 / 总周期",
        "uncalculable_rule": "周期参数缺失",
    },
    "progress_gap": {
        "name": "进度偏差",
        "unit": "百分点",
        "definition": "达成率 - 序时进度",
        "uncalculable_rule": "达成率或序时进度不可计算",
    },
    "activity_rate": {
        "name": "活动率",
        "unit": "%",
        "definition": "活动人力 / 在职人力",
        "uncalculable_rule": "在职人力为 0 或缺失",
    },
    "avg_premium": {
        "name": "人均保费",
        "unit": "万元/人",
        "definition": "月均新单保费 / 月均在职人力",
        "uncalculable_rule": "月均在职人力为 0 或缺失",
    },
    "avg_productivity": {
        "name": "人均产能",
        "unit": "万元/人",
        "definition": "新单保费 / 月均活动人力",
        "uncalculable_rule": "月均活动人力为 0 或缺失",
    },
    "conversion_rate": {
        "name": "转化率",
        "unit": "%",
        "definition": "成交数 / 触达或线索数",
        "uncalculable_rule": "基数为 0 或缺失",
    },
    "expense_rate": {
        "name": "费用率",
        "unit": "%",
        "definition": "费用 / 保费",
        "uncalculable_rule": "保费为 0 或缺失",
    },
    "roi": {
        "name": "投产比",
        "unit": "倍",
        "definition": "产出 / 投入",
        "uncalculable_rule": "投入为 0 或缺失",
    },
}

# 前端展示约束
DISPLAY_CONSTRAINTS = {
    "activity_rate_yoy": {
        "description": "长险活动率同比按百分点差展示",
        "unit": "pp",
        "formula": "本期活动率 - 上年同期活动率",
        "note": "不使用相对增速",
    },
    "incomplete_data": {
        "description": "聚合表暂无完整数据支撑时的展示约束",
        "rule": "前端展示为空状态或'口径待完善'，不得默认展示 0% 作为达成结果",
        "examples": ["长险期交", "保障类产品"],
    },
    "target_fallback": {
        "description": "服务端目标返回 categories: null 时的降级策略",
        "rule": "前端可使用默认目标保证页面可用，但必须标明'服务端尚未配置正式目标'",
    },
}

__all__ = ["METRICS", "DISPLAY_CONSTRAINTS"]
