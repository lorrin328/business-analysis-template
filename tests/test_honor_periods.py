from datetime import date

from honor.periods import honor_final_ready_on, honor_month_end, honor_result_meta


def test_honor_result_meta_distinguishes_process_month_end_observation_and_final():
    today = date(2026, 8, 3)

    process = honor_result_meta(2026, 7, "2026-07-27", today=today)
    month_end = honor_result_meta(2026, 7, "2026-07-31", today=today)
    observation = honor_result_meta(2026, 7, "2026-08-03", today=today)
    final = honor_result_meta(2026, 7, None, today=today)

    assert honor_month_end(2026, 7).isoformat() == "2026-07-31"
    assert honor_final_ready_on(2026, 7).isoformat() == "2026-09-14"
    assert process["resultType"] == "process"
    assert process["resultLabel"] == "截至7月27日（过程）"
    assert month_end["resultType"] == "month_end"
    assert month_end["resultLabel"] == "7月31日（月末快照）"
    assert observation["resultType"] == "observation"
    assert observation["resultLabel"] == "回销观察更新至8月3日"
    assert final["resultType"] == "final"
    assert final["canCreateFinal"] is False
    assert final["finalConfirmed"] is False
    assert "请核对回销数据是否完整" in final["resultNote"]


def test_honor_final_becomes_ready_after_full_callback_observation():
    meta = honor_result_meta(
        2026,
        7,
        None,
        today=date(2026, 9, 14),
        created_at="2026-09-14 09:00:00",
    )

    assert meta["canCreateMonthEndSnapshot"] is True
    assert meta["canCreateFinal"] is True
    assert meta["finalConfirmed"] is True
    assert "完成45天回销观察" in meta["resultNote"]


def test_honor_legacy_final_created_too_early_keeps_warning_after_ready_date():
    meta = honor_result_meta(
        2026,
        7,
        None,
        today=date(2026, 10, 1),
        created_at="2026-08-03 09:00:00",
    )

    assert meta["canCreateFinal"] is True
    assert meta["finalConfirmed"] is False
    assert "请核对回销数据是否完整" in meta["resultNote"]
