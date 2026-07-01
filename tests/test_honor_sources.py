from honor.sources import metric_for_staff


def test_honor_metric_for_staff_combines_personal_and_qualified_team_metric():
    policy_index = {
        "personal": {
            (2026, 5, "00001001", "OTO"): {
                "premium": 20_000,
                "policy_count": 1,
                "qualified": True,
                "protected": False,
            }
        },
        "supervisor": {
            (2026, 5, "00001001", "OTO"): {
                "premium": 100_000,
                "policy_count": 4,
                "qualified": True,
                "protected": False,
            }
        },
        "manager": {},
    }

    metric = metric_for_staff(policy_index, 2026, 5, "00001001", "OTO", "主管")

    assert metric["premium"] == 120_000
    assert metric["policy_count"] == 5
    assert metric["earned_diamonds"] == 2
    assert metric["personal_qualified"] is True
    assert metric["team_qualified"] is True


def test_honor_metric_for_staff_falls_back_to_personal_metric():
    policy_index = {
        "personal": {
            (2026, 5, "00001001", "OTO"): {
                "premium": 20_000,
                "policy_count": 1,
                "qualified": True,
                "protected": False,
            }
        },
        "supervisor": {
            (2026, 5, "00001001", "OTO"): {
                "premium": 90_000,
                "policy_count": 3,
                "qualified": False,
                "protected": False,
            }
        },
        "manager": {},
    }

    metric = metric_for_staff(policy_index, 2026, 5, "00001001", "OTO", "主管")

    assert metric["premium"] == 20_000
    assert metric["policy_count"] == 1
    assert metric["earned_diamonds"] == 1
