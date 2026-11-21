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
