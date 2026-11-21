# -*- coding: utf-8 -*-
"""수집 기간 계산. 모든 시각은 KST(+09:00)."""
import json
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import holidays

from .config import MAX_WINDOW_DAYS, RUN_HOUR, RUN_MINUTE

KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = ROOT / "state" / "last_success.json"
EXTRA_HOLIDAYS_FILE = ROOT / "state" / "extra_holidays.txt"  # 임시공휴일 등 수동 추가 (YYYY-MM-DD, 한 줄에 하나)

WEEKDAYS = "월화수목금토일"


def _extra_holidays():
    if not EXTRA_HOLIDAYS_FILE.exists():
        return set()
    out = set()
    for line in EXTRA_HOLIDAYS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip()
        if line:
            out.add(date.fromisoformat(line))
    return out


def holiday_name(d):
    if d in _extra_holidays():
        return "임시공휴일"
    return holidays.country_holidays("KR", years=d.year).get(d)


def is_business_day(d):
    return d.weekday() < 5 and holiday_name(d) is None


def run_time_on(d):
    return datetime.combine(d, time(RUN_HOUR, RUN_MINUTE), tzinfo=KST)


def previous_business_day(d):
    d -= timedelta(days=1)
    while not is_business_day(d):
        d -= timedelta(days=1)
    return d


def load_last_success(path=STATE_FILE):
    try:
        return datetime.fromisoformat(json.loads(path.read_text(encoding="utf-8"))["last_success"]).astimezone(KST)
    except (FileNotFoundError, KeyError, ValueError):
        return None


def save_last_success(dt, path=STATE_FILE):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"last_success": dt.astimezone(KST).isoformat(timespec="seconds")}, ensure_ascii=False,
                               indent=1) + "\n", encoding="utf-8")


def compute_window(now, last_success, force=False):
    """(start, end, skip_reason) 반환. skip_reason이 있으면 실행하지 않는다."""
    now = now.astimezone(KST)
    today = now.date()
    if not force:
        if not is_business_day(today):
            return None, None, f"영업일 아님 ({WEEKDAYS[today.weekday()]}요일 {holiday_name(today) or ''})".strip()
        if last_success and last_success >= run_time_on(today) - timedelta(hours=2):
            return None, None, f"오늘 이미 실행됨 ({last_success:%H:%M})"
    if last_success is None or last_success >= now:
        start = run_time_on(previous_business_day(today))
    else:
        start = last_success
    start = max(start, now - timedelta(days=MAX_WINDOW_DAYS))
    return start, now, None


def fmt_kst(dt):
    """11/21(금) 07:30"""
    dt = dt.astimezone(KST)
    return f"{dt.month}/{dt.day}({WEEKDAYS[dt.weekday()]}) {dt:%H:%M}"


def fmt_window(start, end):
    return f"{fmt_kst(start)} ~ {fmt_kst(end)}"
