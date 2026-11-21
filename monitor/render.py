# -*- coding: utf-8 -*-
"""report.json → 반응형 HTML (최신 docs/index.html + 날짜별 보관 + 보관함 목록)."""
import json
import re
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

from .config import HIGHLIGHT_KEYWORDS, WISET_SECTION
from .window import KST, WEEKDAYS

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
TAB_LABELS = {"WISET 직접 언급": "WISET", "정부정책동향": "정부정책", "유관기관동향": "유관기관",
              "여성과학기술인": "여성과기인", "참고보도": "참고보도", "기고칼럼": "기고칼럼"}
IMPORTANCE_LABEL = {"★★★": "즉시 대응", "★★☆": "업무 참고", "★☆☆": "동향 파악"}

_HL = re.compile("|".join(re.escape(k) for k in sorted(HIGHLIGHT_KEYWORDS, key=len, reverse=True)))


def highlight(text):
    """HTML 이스케이프 후 주요 키워드에 <mark>."""
    return Markup(_HL.sub(lambda m: f"<mark>{m.group(0)}</mark>", str(escape(text or ""))))


def kdate(dt):
    return f"{dt.year}년 {dt.month}월 {dt.day}일 {WEEKDAYS[dt.weekday()]}요일"


ENV = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=select_autoescape(["html", "j2"]),
                  trim_blocks=True, lstrip_blocks=True)
ENV.filters["hl"] = highlight


def build_context(report, root):
    end = datetime.fromisoformat(report["end"]).astimezone(KST)
    sections = []
    for i, (name, v) in enumerate(report["sections"].items()):
        sections.append({
            "id": f"s{i + 1}", "name": name, "tab": TAB_LABELS.get(name, name), "wiset": name == WISET_SECTION,
            "items": v["items"], "note": v.get("note"), "candidates": v.get("candidates", 0),
        })
    return {
        "root": root,
        "date_key": end.strftime("%Y-%m-%d"),
        "date_label": kdate(end),
        "short_date": f"{end.month}/{end.day}({WEEKDAYS[end.weekday()]})",
        "window_label": report["window_label"],
        "total": sum(len(s["items"]) for s in sections),
        "sections": sections,
        "generated": datetime.fromisoformat(report["generated"]).astimezone(KST).strftime("%Y-%m-%d %H:%M"),
        "model": report.get("model", ""),
        "imp_label": IMPORTANCE_LABEL,
    }


def write_report(report, docs=DOCS):
    ctx = build_context(report, root="./")
    key = ctx["date_key"]
    (docs / "data").mkdir(parents=True, exist_ok=True)
    (docs / "archive").mkdir(parents=True, exist_ok=True)
    (docs / "data" / f"{key}.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    tpl = ENV.get_template("report.html.j2")
    (docs / "index.html").write_text(tpl.render(**ctx, is_latest=True), encoding="utf-8")
    ctx_a = build_context(report, root="../")
    (docs / "archive" / f"{key}.html").write_text(tpl.render(**ctx_a, is_latest=False), encoding="utf-8")
    write_archive_index(docs)
    return key


def write_archive_index(docs=DOCS):
    rows = []
    for f in sorted((docs / "data").glob("*.json"), reverse=True):
        try:
            r = json.loads(f.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        end = datetime.fromisoformat(r["end"]).astimezone(KST)
        counts = {TAB_LABELS.get(k, k): len(v["items"]) for k, v in r["sections"].items()}
        rows.append({"key": f.stem, "label": kdate(end), "window": r["window_label"],
                     "total": sum(counts.values()), "wiset": counts.get("WISET", 0)})
    html = ENV.get_template("archive.html.j2").render(rows=rows, root="../")
    (docs / "archive" / "index.html").write_text(html, encoding="utf-8")
