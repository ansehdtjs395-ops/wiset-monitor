from monitor import select_ai
from monitor.select_ai import Selector


def art(i, title, sub="과학기술정보통신부", desc="설명"):
    return {"title": title, "desc": desc, "link": f"https://x/{i}", "source": "조선일보", "sub": sub,
            "pub": f"2026-11-20T0{i % 10}:00+09:00", "keyword": "과기부", "section": "정부정책동향"}


def make(monkeypatch, responses):
    s = Selector.__new__(Selector)
    s.log = lambda *_: None
    s.usage = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "calls": 0}
    s.fatal = None
    calls = []

    def fake(section, lines, user=None):
        calls.append(lines if lines is not None else ["MERGE"])
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


def test_merge_across_chunks(monkeypatch):
    monkeypatch.setattr(select_ai, "CHUNK", 2)
    arts = [art(i, f"T{i}") for i in range(4)]
    s, calls = make(monkeypatch, [
        [{"id": 0, "summary": "s0", "importance": "★★☆", "author": "", "related_ids": []}],
        [{"id": 2, "summary": "s2", "importance": "★☆☆", "author": "", "related_ids": [3]}],
        [{"id": 1, "summary": "", "importance": "★★☆", "author": "", "related_ids": [0]}],  # 합치기: T2가 대표, T0 묶음
    ])
    items, _ = s.select_section("정부정책동향", {"과학기술정보통신부": arts})
    assert calls[-1] == ["MERGE"] and len(items) == 1
    assert items[0]["title"] == "T2" and items[0]["summary"] == "s2"
    assert {r["title"] for r in items[0]["related"]} == {"T3", "T0"}


def test_resolve_id():
    from monitor.select_ai import resolve_id
    titles = ["사학연금-화순군 협약", "한국전력KDN 청렴 특강", "과기부 AI 예산"]
    assert resolve_id({"id": 1, "title_start": "한국전력KDN 청"}, titles) == 1
    assert resolve_id({"id": 0, "title_start": "한국전력KDN 청"}, titles) == 1   # 잘못된 id → 제목으로 교정
    assert resolve_id({"id": 0, "title_start": "없는 제목입니다"}, titles) is None
    assert resolve_id({"id": 12, "title_start": "과기부 AI"}, titles, offset=10) == 2


def test_resolve_id_tolerant():
    from monitor.select_ai import resolve_id
    titles = ["기타 기사", "국립목포대,여성 과학기술인 역량 강화 교육 실시"]
    assert resolve_id({"id": 1, "title_start": "[필수] 국립목대,여성"}, titles) == 1


def test_resolve_id_bracket_prefix():
    from monitor.select_ai import resolve_id
    titles = ["기타", '[이로운분석] "재취업 7년반 걸렸어요"...경력단절여성은 서럽다']
    assert resolve_id({"id": 0, "title_start": "재취업 7년반 걸렸어요 경력단절"}, titles) == 1


def test_apply_moves():
    from monitor.select_ai import apply_moves

    def it(title, sec, move="", alts=None, imp="★☆☆"):
        return {"title": title, "desc": "", "link": f"https://x/{title}", "source": "여성신문", "sub": "s",
                "pub": "2026-11-20T00:00+09:00", "importance": imp, "move_to": move, "alt_sections": alts or {},
                "section": sec, "summary": "", "author": "", "related": []}
    res = {
        "유관기관동향": {"items": [it("연재", "유관기관동향", "여성과학기술인", {"여성과학기술인": "여성 과학자·연구자"}),
                               it("엉뚱", "유관기관동향", "기고칼럼")], "note": None, "candidates": 2},
        "여성과학기술인": {"items": [it("임금격차", "여성과학기술인", "참고보도")], "note": None, "candidates": 1},
        "WISET 직접 언급": {"items": [it("WISET 포럼", "WISET 직접 언급", "참고보도")], "note": None, "candidates": 1},
        "참고보도": {"items": [], "note": None, "candidates": 0},
    }
    apply_moves(res, log=lambda *_: None)
    titles = {k: [a["title"] for a in v["items"]] for k, v in res.items()}
    assert titles["유관기관동향"] == ["엉뚱"]          # 걸리지 않은 섹션(기고칼럼)으로는 못 옮김
    assert titles["여성과학기술인"] == ["연재"]
    assert res["여성과학기술인"]["items"][0]["sub"] == "여성 과학자·연구자"
    assert titles["참고보도"] == ["임금격차"]           # 참고보도는 키워드 없이도 옮길 수 있음
    assert titles["WISET 직접 언급"] == ["WISET 포럼"]  # WISET 섹션은 옮기지 않음


def test_call_cost_tiers():
    from monitor.select_ai import call_cost
    # 11/23 실제 사용량(9회 합계, 호출마다 10만 토큰 이하)을 기본 단가로 계산하면 기록된 $0.0344와 같다
    total = {"input": 234_723, "output": 20_041, "cache_read": 36_056, "cache_write": 4_507}
    assert round(sum(total[k] * p for k, p in select_ai.PRICE.items()) / 1e6, 4) == 0.0344
    small = {"input": 60_000, "output": 2_000, "cache_read": 4_500, "cache_write": 0}
    big = {**small, "input": 120_000}
    assert abs(call_cost(small) - (60_000 * 0.10 + 2_000 * 0.50 + 4_500 * 0.01) / 1e6) < 1e-12
    assert abs(call_cost(big) - (120_000 * 0.50 + 2_000 * 2.50 + 4_500 * 0.05) / 1e6) < 1e-12


def test_system_prompt_rules():
    sp = select_ai.SYSTEM
    assert "수산정책" in sp and "산업보안한림원" in sp and "남녀 임금 격차" in sp
    assert "사진 설명" in sp and "move_to" in sp
