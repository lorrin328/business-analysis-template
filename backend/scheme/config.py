from __future__ import annotations

from datetime import date

SCHEME_ID = "2026-org-dev-policy"
SCHEME_NAME = "2026年组发政策"
RULE_VERSION = "2026-org-dev-v1"
DATA_SOURCE_MODE = "scheme_excel_upload"

SCHEME_START = date(2026, 7, 1)
SCHEME_END = date(2026, 12, 31)
ENTRY_START = date(2026, 7, 1)
ENTRY_END = date(2026, 9, 30)
MONTHS = [7, 8, 9, 10, 11, 12]

SCHEME_OPTIONS = [
    {
        "id": SCHEME_ID,
        "name": SCHEME_NAME,
        "ruleVersion": RULE_VERSION,
        "scope": "网电多元系列 OTO 条线",
        "period": {"start": SCHEME_START.isoformat(), "end": SCHEME_END.isoformat()},
        "entryWindow": {"start": ENTRY_START.isoformat(), "end": ENTRY_END.isoformat()},
        "sourceFileHint": "组织发展追踪模板.xlsx",
        "status": "active",
    }
]

RULE_DEFINITIONS = {
    "standardPremium": "首期标保按政策附件折算：趸交×0.1、3年交×0.3、5年交×0.5、10年及以上×1。",
    "activeManpower": "当月净承保长险件数大于等于 1 件的人力计为活动人力。",
    "teamManpower": "团队人力仅统计方案期内入职且月末在职人力。",
    "supervisorTeam": "入职主管团队标准：1-2月 1+2 且开单率50%；3-4月另需首期标保4万；5-6月 1+3、开单率60%、首期标保6万。",
    "managerTeam": "入职经理团队标准：1-2月 1+2+4 且开单率50%；3-4月另需首期标保10万；5-6月 1+2+6、开单率60%、首期标保14万。",
    "maintain": "未达成但团队首期标保达到对应阶段标准的70%时，不发放当月奖励但保留次月参与资格；低于70%自当月起淘汰。",
    "recommendAward": "推荐人当月为活动人力，且其推荐新人团队达标时，推荐人奖励1000元/月/团队。",
    "organizationAward": "育成团队达标后，组织育成奖原则上发放给晋升人员原主管；无主管则发放给原经理。",
    "starAward": "星钻育成奖为团队当月首期标保的2%，需满足星钻联盟团队标准。",
    "policyValidity": "有效保单需满足承保、回执回访、犹豫期、45日内未撤保退保且排除自保互保等条件。",
}
