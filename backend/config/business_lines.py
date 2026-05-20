BUSINESS_LINES = [
    {
        "code": "jingdai",
        "name": "经代",
        "displayName": "经代",
        "color": "#8b5cf6",
        "order": 10,
        "isIncludedInTotal": True,
        "supportOrgDimension": False,
        "supportTeamDimension": False,
        "supportDailyTrend": True,
        "aliases": ["经代"],
    },
    {
        "code": "oto",
        "name": "OTO",
        "displayName": "OTO",
        "color": "#3b82f6",
        "order": 20,
        "isIncludedInTotal": True,
        "supportOrgDimension": True,
        "supportTeamDimension": True,
        "supportDailyTrend": True,
        "aliases": ["OTO"],
    },
    {
        "code": "zhengbao",
        "name": "证保",
        "displayName": "证保",
        "color": "#10b981",
        "order": 30,
        "isIncludedInTotal": True,
        "supportOrgDimension": True,
        "supportTeamDimension": True,
        "supportDailyTrend": True,
        "aliases": ["证保", "证券"],
    },
    {
        "code": "yiqiao",
        "name": "蚁桥",
        "displayName": "蚁桥",
        "color": "#f59e0b",
        "order": 40,
        "isIncludedInTotal": True,
        "supportOrgDimension": True,
        "supportTeamDimension": True,
        "supportDailyTrend": True,
        "aliases": ["蚁桥", "网服"],
    },
    {
        "code": "transform",
        "name": "转型业务",
        "displayName": "转型业务",
        "color": "#14b8a6",
        "order": 50,
        "isIncludedInTotal": True,
        "supportOrgDimension": True,
        "supportTeamDimension": True,
        "supportDailyTrend": True,
        "aliases": ["转型业务"],
    },
    {
        "code": "total",
        "name": "整体业务",
        "displayName": "整体业务",
        "color": "#e2e8f0",
        "order": 60,
        "isIncludedInTotal": False,
        "supportOrgDimension": False,
        "supportTeamDimension": False,
        "supportDailyTrend": True,
        "aliases": ["整体", "整体业务"],
    },
]

BUSINESS_LINE_BY_NAME = {
    alias: item
    for item in BUSINESS_LINES
    for alias in [item["name"], item["displayName"], *item.get("aliases", [])]
}


CHANNEL_MAP = {'证券': '证保', '网服': '蚁桥'}
TRANSFORM_CHANNELS = {'OTO', '证保', '蚁桥'}

import os
from datetime import datetime

DEFAULT_YEAR = int(os.getenv("DEFAULT_YEAR", str(datetime.now().year)))


def normalize_business_line(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    item = BUSINESS_LINE_BY_NAME.get(text)
    return item["name"] if item else text


def line_supports_org(value: str | None) -> bool:
    item = BUSINESS_LINE_BY_NAME.get(str(value).strip()) if value is not None else None
    return bool(item and item.get("supportOrgDimension"))
