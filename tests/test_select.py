from monitor import select_ai
from monitor.select_ai import Selector


def art(i, title, sub="과학기술정보통신부", desc="설명"):
    return {"title": title, "desc": desc, "link": f"https://x/{i}", "source": "조선일보", "sub": sub,
            "pub": f"2026-11-20T0{i % 10}:00+09:00", "keyword": "과기부", "section": "정부정책동향"}


def make(monkeypatch, responses):
    s = Selector.__new__(Selector)
    s.log = lambda *_: None
    s.usage = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "calls": 0}
    calls = []

    def fake(section, lines):
        calls.append(lines)
        r = responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r
    monkeypatch.setattr(s, "_call", fake)
    return s, calls


def test_select_groups_and_sorts(monkeypatch):
    arts = [art(0, "A"), art(1, "B"), art(2, "C")]
    s, _ = make(monkeypatch, [[
        {"id": 2, "summary": "요약C", "importance": "★☆☆", "author": "", "related_ids": []},
        {"id": 0, "summary": "요약A", "importance": "★★☆", "author": "", "related_ids": [1, 99]},
    ]])
    items, note = s.select_section("정부정책동향", {"과학기술정보통신부": arts})
    assert note is None and [i["title"] for i in items] == ["A", "C"]
    assert [r["title"] for r in items[0]["related"]] == ["B"]


def test_forced_wiset_added_and_fallback(monkeypatch):
    arts = [art(0, "WISET, 여학생 공학주간 개최", sub="WISET 관련"), art(1, "기타", sub="WISET 관련")]
    s, _ = make(monkeypatch, [[]])
    items, _ = s.select_section("WISET 직접 언급", {"WISET 관련": arts})
    assert [i["title"] for i in items] == ["WISET, 여학생 공학주간 개최"] and items[0]["importance"] == "★★★"

    s, _ = make(monkeypatch, [RuntimeError("x"), RuntimeError("y")])
    items, note = s.select_section("정부정책동향", {"과학기술정보통신부": [art(0, "A")]})
    assert note and "실패" in note and len(items) == 1


def test_chunking(monkeypatch):
    monkeypatch.setattr(select_ai, "CHUNK", 2)
    arts = [art(i, f"T{i}") for i in range(5)]
    s, calls = make(monkeypatch, [[], [{"id": 3, "summary": "s", "importance": "★★☆", "author": "",
                                        "related_ids": [2]}], []])
    items, _ = s.select_section("정부정책동향", {"과학기술정보통신부": arts})
    assert len(calls) == 3 and calls[1][0].startswith("2 |")
    assert items[0]["title"] == "T3" and items[0]["related"][0]["title"] == "T2"


def test_system_prompt_has_examples():
    assert "AI 동료과학자" in select_ai.SYSTEM and "포르쉐" in select_ai.SYSTEM
