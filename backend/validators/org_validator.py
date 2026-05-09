from config.business_lines import line_supports_org


def org_scope_note(business_lines: list[str], selected_orgs: list[str] | None = None) -> str:
    selected_orgs = selected_orgs or []
    if selected_orgs and any(line == "经代" and not line_supports_org(line) for line in business_lines):
        return "经代暂无机构维度，当前经代数据按整体口径展示。"
    return ""
