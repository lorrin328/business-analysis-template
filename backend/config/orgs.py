ORG_LIST = ["上海", "湖北", "四川", "辽宁", "山东", "广东", "福建", "浙江", "河南", "北京"]
ORG_SCOPE = set(ORG_LIST)


def normalize_org(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
