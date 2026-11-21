from datetime import datetime

from monitor.window import KST, compute_window, fmt_window


def t(s):
    return datetime.fromisoformat(s).replace(tzinfo=KST)


def test_tuesday_from_monday_0730():
    s, e, skip = compute_window(t("2026-11-24T07:30"), t("2026-11-23T07:31"))
    assert skip is None and s == t("2026-11-23T07:31") and e == t("2026-11-24T07:30")


def test_monday_includes_weekend():
    s, e, skip = compute_window(t("2026-11-23T07:30"), t("2026-11-20T07:30"))
    assert skip is None and s == t("2026-11-20T07:30")
    assert fmt_window(s, e) == "11/20(금) 07:30 ~ 11/23(월) 07:30"


def test_first_run_monday_falls_back_to_friday():
    s, _, _ = compute_window(t("2026-11-23T07:30"), None)
    assert s == t("2026-11-20T07:30")


def test_day_after_holiday_merges():
    # 2026-10-05(월) 개천절 대체휴일 → 10-06(화)은 10-02(금) 이후 전부
    s, _, skip = compute_window(t("2026-10-06T07:30"), t("2026-10-02T07:30"))
    assert skip is None and s == t("2026-10-02T07:30")


def test_first_run_after_holiday_falls_back_past_holiday():
    s, _, _ = compute_window(t("2026-10-06T07:30"), None)
    assert s == t("2026-10-02T07:30")


def test_after_failed_run_uses_last_success():
    s, _, _ = compute_window(t("2026-11-26T07:30"), t("2026-11-24T07:30"))
    assert s == t("2026-11-24T07:30")


def test_holiday_skips():
    _, _, skip = compute_window(t("2026-12-25T07:30"), t("2026-12-24T07:30"))
    assert skip and "기독탄신일" in skip


def test_weekend_skips():
    _, _, skip = compute_window(t("2026-11-22T07:30"), t("2026-11-20T07:30"))
    assert skip


def test_second_run_same_day_skips():
    _, _, skip = compute_window(t("2026-11-24T12:40"), t("2026-11-24T07:31"))
    assert skip and "이미" in skip


def test_delayed_run_still_runs():
    # GitHub 예약이 늦어 12:40에 처음 실행돼도 수집
    s, e, skip = compute_window(t("2026-11-24T12:40"), t("2026-11-23T07:30"))
    assert skip is None and s == t("2026-11-23T07:30") and e == t("2026-11-24T12:40")


def test_window_capped():
    s, _, _ = compute_window(t("2026-11-24T07:30"), t("2026-10-01T07:30"))
    assert s == t("2026-11-14T07:30")
