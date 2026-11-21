import json

from monitor.render import highlight, write_report


def report(end="2026-11-23T07:30:00+09:00"):
    item = {"title": "과기부 <script>x</script> 발표", "summary": "KAIST와 WISET 협력", "importance": "★★☆",
            "author": "", "source": "조선일보", "link": "https://e.x/1", "sub": "과학기술정보통신부", "pub": end,
            "related": [{"title": "관련", "source": "뉴스1", "link": "https://e.x/2"}]}
    return {"generated": end, "start": "2026-11-20T07:30:00+09:00", "end": end, "model": "claude-haiku-5-5",
            "window_label": "11/20(금) 07:30 ~ 11/23(월) 07:30",
            "sections": {"WISET 직접 언급": {"items": [], "note": None, "candidates": 0},
                         "정부정책동향": {"items": [item], "note": "AI 선별 실패: 테스트", "candidates": 3}}}


def test_highlight_escapes():
    h = str(highlight("과기부 <b>KAIST</b>"))
    assert "<mark>과기부</mark>" in h and "&lt;b&gt;<mark>KAIST</mark>&lt;/b&gt;" in h


def test_write_report_and_archive(tmp_path):
    key = write_report(report(), docs=tmp_path)
    assert key == "2026-11-23"
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "2026년 11월 23일 월요일" in html and "11/20(금) 07:30 ~ 11/23(월) 07:30" in html
    assert "총 1건" in html and "<script>x" not in html and "관련 기사 1건" in html
    assert "이번 수집 기간에 해당 기사가 없습니다" in html and "AI 선별 실패: 테스트" in html
    assert 'target="_blank"' in html
    arch = (tmp_path / "archive" / "2026-11-23.html").read_text(encoding="utf-8")
    assert 'href="../manifest.webmanifest"' in arch
    write_report(report("2026-11-24T07:30:00+09:00"), docs=tmp_path)
    idx = (tmp_path / "archive" / "index.html").read_text(encoding="utf-8")
    assert idx.index("2026-11-24.html") < idx.index("2026-11-23.html")
    assert json.loads((tmp_path / "data" / "2026-11-24.json").read_text(encoding="utf-8"))["end"].startswith("2026-11-24")
