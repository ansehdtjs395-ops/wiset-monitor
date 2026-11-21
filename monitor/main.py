# -*- coding: utf-8 -*-
"""실행 진입점.

python -m monitor.main                         # 지금 시각 기준 실행
python -m monitor.main --now 2026-11-23T07:30+09:00 --dry-run
옵션
  --now       실행 시각 가정 (테스트용, KST ISO 형식)
  --dry-run   state/last_success.json 을 갱신하지 않음
  --force     휴일·중복 실행 검사 건너뜀
  --collect-only  수집까지만 하고 out/candidates.json 저장
"""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from . import window
from .naver import NaverClient, collect
from .render import write_report
from .select_ai import MODEL, Selector

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--now")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--collect-only", action="store_true")
    ap.add_argument("--start", help="수집 시작 시각 강제 지정 (테스트용)")
    ap.add_argument("--from-candidates", help="수집을 건너뛰고 저장된 candidates.json 사용 (테스트용)")
    args = ap.parse_args(argv)

    now = datetime.fromisoformat(args.now).astimezone(window.KST) if args.now else datetime.now(window.KST)
    last = window.load_last_success()
    if args.now and args.dry_run and last and last >= now:
        last = None  # 과거 시각을 가정한 테스트에서는 기록 무시
    start, end, skip = window.compute_window(now, last, force=args.force)
    print(f"실행 시각(KST): {now:%Y-%m-%d %H:%M} / 마지막 성공: {last:%Y-%m-%d %H:%M}" if last else
          f"실행 시각(KST): {now:%Y-%m-%d %H:%M} / 마지막 성공: 기록 없음")
    if args.start and not skip:
        start = datetime.fromisoformat(args.start).astimezone(window.KST)
    if skip:
        print(f"건너뜀: {skip}")
        return 0
    print(f"수집 기간: {window.fmt_window(start, end)}")

    if args.from_candidates:
        saved = json.loads(Path(args.from_candidates).read_text(encoding="utf-8"))
        candidates, meta = saved["sections"], saved["meta"]
        start, end = datetime.fromisoformat(meta["start"]), datetime.fromisoformat(meta["end"])
        print(f"저장된 후보 사용: {args.from_candidates} ({meta['window_label']})")
    else:
        missing = [k for k in ("NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET") if not os.environ.get(k)]
        if missing:
            print(f"오류: 환경변수 {', '.join(missing)} 가 없습니다. GitHub Secrets에 등록돼 있는지 확인하세요.")
            return 1
        client = NaverClient(os.environ["NAVER_CLIENT_ID"], os.environ["NAVER_CLIENT_SECRET"])
        candidates, stats = collect(client, start, end)
        print(f"수집 결과: 원본 {stats['raw']}건 → 제외: 검색어가 제목·설명에 없음 {stats['offtopic']}건, "
              f"주요 언론사 아님 {stats['minor']}건, 중복 {stats['dup']}건, 사전필터 {stats['prefiltered']}건 → "
              f"후보 {stats['kept']}건 (API 호출 {stats['calls']}회)")
        for sec, subs in candidates.items():
            print(f"  - {sec}: {sum(len(v) for v in subs.values())}건")
        for w in client.warnings:
            print("경고:", w)

        OUT.mkdir(exist_ok=True)
        meta = {"now": now.isoformat(), "start": start.isoformat(), "end": end.isoformat(),
                "window_label": window.fmt_window(start, end), "stats": stats}
        (OUT / "candidates.json").write_text(json.dumps({"meta": meta, "sections": candidates}, ensure_ascii=False,
                                                        indent=1), encoding="utf-8")
    if args.collect_only:
        return 0

    key = os.environ.get("CLAUDE_API_KEY")
    if not key:
        print("오류: 환경변수 CLAUDE_API_KEY 가 없습니다. GitHub Secrets에 등록돼 있는지 확인하세요.")
        return 1
    print(f"AI 선별 ({MODEL})")
    sel = Selector(key)
    selected = sel.select_all(candidates)
    u = sel.usage
    print(f"AI 사용량: 호출 {u['calls']}회, 입력 {u['input']:,} / 출력 {u['output']:,} / 캐시읽기 {u['cache_read']:,} / "
          f"캐시쓰기 {u['cache_write']:,} 토큰 → 예상 비용 ${sel.cost():.4f}")
    report = {"generated": now.isoformat(), "start": start.isoformat(), "end": end.isoformat(),
              "window_label": window.fmt_window(start, end), "model": MODEL,
              "usage": {**u, "cost_usd": round(sel.cost(), 5)}, "sections": selected}
    OUT.mkdir(exist_ok=True)
    (OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    for sec, v in selected.items():
        print(f"\n◆ {sec} ({len(v['items'])}건 / 후보 {v['candidates']}건)" + (f" ※ {v['note']}" if v["note"] else ""))
        for it in v["items"]:
            rel = f" [관련 기사 {len(it['related'])}건]" if it["related"] else ""
            au = f" — {it['author']}" if it["author"] else ""
            print(f"  {it['importance']} ({it['source']}) {it['title']}{au}{rel}\n      {it['summary']}")

    if args.dry_run:
        preview = OUT / "preview"
        key = write_report(report, docs=preview)
        print(f"\n미리보기 저장: {preview / 'index.html'} ({key})")
    else:
        key = write_report(report)
        window.save_last_success(end)
        print(f"\n리포트 저장: docs/index.html, docs/archive/{key}.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
