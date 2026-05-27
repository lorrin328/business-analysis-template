import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from auth import default_permissions_for_role


def test_honor_default_permissions():
    admin = default_permissions_for_role("admin")
    senior = default_permissions_for_role("senior")
    normal = default_permissions_for_role("normal")

    assert all(admin[key] for key in ["honor_view", "honor_audit", "honor_recalculate", "honor_export", "honor_admin"])
    assert senior["honor_view"] is True
    assert senior["honor_audit"] is True
    assert senior["honor_recalculate"] is True
    assert senior["honor_export"] is True
    assert senior["honor_admin"] is False
    assert senior["honor_upload"] is False
    assert normal["honor_view"] is True
    assert normal["honor_audit"] is False
    assert normal["honor_recalculate"] is False
    assert normal["honor_export"] is False
