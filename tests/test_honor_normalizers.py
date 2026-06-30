from honor.normalizers import (
    normalize_business_line,
    number_value,
    optional_int,
    parse_date,
    role_type,
    staff_code,
    text_value,
    ym_from_value,
)


def test_honor_text_and_staff_code_normalization():
    assert text_value(" 123.0 ") == "123"
    assert text_value(None) == ""
    assert staff_code("123") == "00000123"
    assert staff_code("A123") == "A123"
    assert staff_code(None) == ""


def test_honor_numeric_normalization():
    assert number_value("12.5") == 12.5
    assert number_value("") == 0.0
    assert number_value("bad") == 0.0
    assert optional_int("2026.0") == 2026
    assert optional_int(None) is None


def test_honor_date_and_period_normalization():
    assert parse_date("2026-06-30 12:13:14").year == 2026
    assert parse_date("2026/06/30").month == 6
    assert parse_date("bad") is None
    assert ym_from_value("202606") == (2026, 6)
    assert ym_from_value("2026-05-01") == (2026, 5)
    assert ym_from_value("bad") == (None, None)


def test_honor_business_line_and_role_normalization():
    assert normalize_business_line("证券") == "证保"
    assert normalize_business_line("网服") == "蚁桥"
    assert normalize_business_line("OTO") == "OTO"
    assert role_type("创新经理") == "经理"
    assert role_type("创新主管") == "主管"
    assert role_type("服务经理") == "主管"
    assert role_type("客户经理") == "个人"
