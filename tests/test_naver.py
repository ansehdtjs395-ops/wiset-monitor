from datetime import datetime, timedelta
from email.utils import format_datetime

from monitor.naver import NaverClient, collect, norm_title, source_of
from monitor.window import KST


class FakeResp:
    def __init__(self, data):
        self.status_code, self._d, self.text = 200, data, ""

    def json(self):
        return self._d


class FakeSession:
    """키워드마다 end부터 1시간 간격으로 기사 n개를 최신순으로 돌려준다."""

    def __init__(self, end, n=250):
        self.end, self.n, self.calls = end, n, []

    def get(self, url, headers, params, timeout):
        self.calls.append(params)
        s = params["start"]
        items = []
        for i in range(s - 1, min(s - 1 + params["display"], self.n)):
            pub = self.end - timedelta(hours=i, minutes=1)
            items.append({"title": f"{params['query']} 기사 {i}", "description": "<b>설명</b>",
                          "originallink": f"https://www.chosun.com/{params['query']}/{i}",
                          "link": f"https://n.news.naver.com/{i}", "pubDate": format_datetime(pub)})
        return FakeResp({"items": items})


def test_pagination_stops_at_window_start():
    end = datetime(2026, 11, 23, 7, 30, tzinfo=KST)
    start = end - timedelta(days=3)  # 72시간 → 기사 72개, 페이지 1개
    sess = FakeSession(end)
    c = NaverClient("id", "sec", session=sess, sleep=0)
    out = c.search_window("과기부", start, end)
    assert len(out) == 72 and len(sess.calls) == 1
    assert all(start <= datetime.fromisoformat(a["pub"]) < end for a in out)
    assert out[0]["desc"] == "설명" and out[0]["source"] == "조선일보"


def test_pagination_multiple_pages():
    end = datetime(2026, 11, 23, 7, 30, tzinfo=KST)
    start = end - timedelta(hours=150)
    sess = FakeSession(end)
    out = NaverClient("id", "sec", session=sess, sleep=0).search_window("KIST", start, end)
    assert len(out) == 150 and [p["start"] for p in sess.calls] == [1, 101]


def test_collect_dedups_across_sections(monkeypatch):
    import monitor.naver as nv
    monkeypatch.setattr(nv, "SECTIONS", {"A": {"a": ["x", "y"]}, "B": {"b": ["x"]}})
    end = datetime(2026, 11, 23, 7, 30, tzinfo=KST)
    c = NaverClient("id", "sec", session=FakeSession(end, n=5), sleep=0)
    res, stats = collect(c, end - timedelta(days=1), end, log=lambda *_: None)
    assert len(res["A"]["a"]) == 10 and res["B"]["b"] == [] and stats["dup"] == 5


def test_helpers():
    assert source_of("https://biz.chosun.com/x") == "조선비즈"
    assert source_of("https://www.etnews.com/1") == "전자신문"
    assert source_of("https://unknown.example.kr/a") == "unknown.example.kr"
    assert norm_title("[단독] 과기부, AI 인재(종합)") == norm_title("과기부 AI 인재")


def test_keyword_rules():
    from monitor.naver import keyword_in_text
    a = lambda kw, title, desc="", src="조선일보": {"keyword": kw, "title": title, "desc": desc, "source": src}
    assert keyword_in_text(a("여성 최초", "서강대 교수, 물리학 여성 최초 한림원 정회원"))
    assert keyword_in_text(a("여성 최초", "물리학 여성최초 정회원"))
    assert not keyword_in_text(a("여성 최초", "20대 여성 실형", "최초 보도"))
    assert keyword_in_text(a("교육부+과학", "교육부 발표", "과학 인재 양성"))
    assert keyword_in_text(a("일가정양립+연구", "일·가정 양립 정책", "연구 결과"))
    assert keyword_in_text(a("대덕넷", "출연연 소식", "", "대덕넷"))
    assert not keyword_in_text(a("대덕넷", "출연연 소식", "", "조선일보"))


def test_strip_caption():
    from monitor.naver import strip_caption
    gdnet = ("류제명 과학기술정보통신부 제2차관이 18일 서울 종로구 정부서울청사에서 독자 AI파운데이션모델 프로젝트 "
             "2차 단계평가 결과 브리핑을 하고 있다. 2026.8.18 (사진=뉴스1) 실질적인 기술 주권을 확보하려면 특정 공급업체...")
    assert strip_caption(gdnet) == "실질적인 기술 주권을 확보하려면 특정 공급업체..."
    assert strip_caption("장관이 발표하고 있다./사진=과기정통부 제공 과기정통부는 23일 계획을 발표했다.") == \
        "과기정통부는 23일 계획을 발표했다."
    plain = "[서울=뉴시스] 홍길동 기자 = 과기정통부가 23일 밝혔다."
    assert strip_caption(plain) == plain
    late = "가" * 200 + " (사진=뉴스1) 뒤"
    assert strip_caption(late) == late  # 뒤쪽 사진 표시는 건드리지 않음


def test_caption_keyword_no_longer_matches():
    """사진 설명에만 '과학기술정보통신부'가 있던 기사는 후보에서 빠진다 (11/23 지디넷 사례)."""
    from monitor.naver import keyword_in_text, strip_caption
    desc = strip_caption("류제명 과학기술정보통신부 제2차관이 브리핑을 하고 있다. 2026.8.18 (사진=뉴스1) 기술 주권을 확보하려면...")
    a = {"keyword": "과학기술정보통신부", "title": "[AI 리더스] 가트너가 내다본 2027년", "desc": desc, "source": "지디넷코리아"}
    assert not keyword_in_text(a)


def test_hallim_keywords():
    from monitor.config import SECTIONS
    from monitor.naver import keyword_in_text
    kws = SECTIONS["유관기관동향"]["과학기술한림원"]
    t = lambda title: any(keyword_in_text({"keyword": k, "title": title, "desc": "", "source": "조선일보"}) for k in kws)
    assert t("한국과학기술한림원, 신입 정회원 선출") and t("한국공학한림원 대상 시상")
    assert not t("한국산업보안한림원, 보안점검지표 91개 개발")


def test_section_prefilter():
    from monitor.naver import prefiltered
    assert prefiltered("정부정책동향", "\"시험지만 남아 있다면\"…교육부, 과거 수능 'AI 부정행위'도 추적 조사")
    assert prefiltered("정부정책동향", "800종 국가시험 개편…수능 커닝 '처벌 5년'")
    assert not prefiltered("정부정책동향", "과기정통부, 연구 부정행위 검증 강화")
    assert not prefiltered("WISET 직접 언급", "수능 부정행위")


def test_collect_alt_sections_and_series(monkeypatch):
    import monitor.naver as nv
    monkeypatch.setattr(nv, "SECTIONS", {"유관기관동향": {"과총·단체": ["x"]}, "여성과학기술인": {"여성 과학자·연구자": ["x"]}})
    monkeypatch.setattr(nv, "SERIES_RULES", [("x 기사 1", "여성과학기술인", "여성 과학자·연구자")])
    end = datetime(2026, 11, 23, 7, 30, tzinfo=KST)
    c = NaverClient("id", "sec", session=FakeSession(end, n=3), sleep=0)
    res, _ = collect(c, end - timedelta(days=1), end, log=lambda *_: None)
    org = res["유관기관동향"]["과총·단체"]
    assert [a["title"] for a in org] == ["x 기사 0", "x 기사 2"]
    assert org[0]["alt_sections"] == {"여성과학기술인": "여성 과학자·연구자"}
    moved = res["여성과학기술인"]["여성 과학자·연구자"]
    assert [a["title"] for a in moved] == ["x 기사 1"] and moved[0]["moved_from"] == "유관기관동향"
