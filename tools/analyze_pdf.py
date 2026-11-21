# -*- coding: utf-8 -*-
"""「언론 및 정책 동향 모니터링」 배포본 PDF 분석.

사용법:  python tools/analyze_pdf.py "<PDF 경로>" <출력폴더>
출력:    items.json (날짜·섹션·태그·제목·메모), stats.txt (통계)
PDF와 출력물은 저장소(공개)에 올리지 않는다. 출력폴더는 저장소 밖을 권장.
"""
import collections as C
import json
import re
import sys
from pathlib import Path

import pymupdf

SECTION_MAP = [
    (r"^(WISET|WSIET)", "WISET"),
    (r"^(간담회|현판식|연차대회)", "WISET"),
    (r"^여성과학", "여성과학기술인"),
    (r"^정부", "정부정책동향"),
    (r"^유관기관", "유관기관동향"),
    (r"^(참고보도|참고보고|국정감사)", "참고보도"),
    (r"^(기고|사설)", "기고칼럼"),
]


def norm_section(raw):
    s = re.sub(r"\s+", "", raw)
    for pat, name in SECTION_MAP:
        if re.match(pat, s):
            return name
    return None


def parse(pdf_path):
    doc = pymupdf.open(pdf_path)
    items = []
    for pno in range(2, len(doc)):  # 1~2쪽은 키워드 목록
        text = doc[pno].get_text()
        m = re.search(r"(\d{4})년\s*(\d+)월\s*(\d+)일\s*(\S+요일)?", text)
        date = f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else None
        weekday = (m.group(4) or "")[:1] if m else ""
        section = None
        last = None
        for line in text.split("\n"):
            line = line.replace("\xa0", " ").strip()
            if not line or "주요 언론보도" in line or re.match(r"^\d{4}년", line):
                continue
            if line.startswith("◆"):
                section = norm_section(line.lstrip("◆ "))
                last = None
                continue
            if line.startswith("ㆍ"):
                last = {"date": date, "weekday": weekday, "section": section, "raw": line[1:].strip()}
                items.append(last)
            elif last is not None:  # 줄바꿈된 제목 이어 붙이기
                last["raw"] += " " + line
    for it in items:
        raw = it["raw"]
        m = re.match(r"\(([^)]*)\)\s*(.*)", raw)
        tag, rest = (m.group(1).strip(), m.group(2)) if m else ("", raw)
        note = ""
        mn = re.search(r"\(([^()]*)\)\s*$", rest)
        if mn and len(rest) - len(mn.group(0)) > 8:
            note = mn.group(1).strip()
            rest = rest[: mn.start()].strip()
        it.update(tag=tag, title=rest.strip(), note=note)
        del it["raw"]
    return items


def main():
    pdf, out = sys.argv[1], Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    items = parse(pdf)
    (out / "items.json").write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")

    lines = []
    p = lines.append
    days = sorted({i["date"] for i in items if i["date"]})
    p(f"기사 {len(items)}건, 리포트 {len(days)}일 ({days[0]} ~ {days[-1]})")
    p(f"섹션 미분류: {sum(1 for i in items if not i['section'])}건")
    recent = [i for i in items if i["date"] and i["date"] >= "2025-01-01"]
    for label, pool in (("전체", items), ("2025~2026", recent)):
        p(f"\n===== {label} =====")
        sec = C.Counter(i["section"] for i in pool)
        nd = len({i["date"] for i in pool})
        for s, n in sec.most_common():
            p(f"{s}: {n}건 (하루 평균 {n / nd:.2f})")
        for s in ["WISET", "여성과학기술인", "정부정책동향", "유관기관동향", "참고보도", "기고칼럼"]:
            sp = [i for i in pool if i["section"] == s]
            p(f"\n## {s} — 태그 상위")
            p(", ".join(f"{k}({v})" for k, v in C.Counter(i["tag"] for i in sp).most_common(30)))
            notes = [i["note"] for i in sp if i["note"]]
            p(f"메모 있는 기사 {len(notes)}건: " + " | ".join(notes[:25]))
            words = C.Counter()
            for i in sp:
                for w in re.findall(r"[가-힣A-Za-z]{2,}", i["title"]):
                    words[w] += 1
            p("제목 단어 상위: " + ", ".join(f"{k}({v})" for k, v in words.most_common(50)))
    (out / "stats.txt").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[:4]))


if __name__ == "__main__":
    main()
