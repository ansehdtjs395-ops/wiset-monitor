# -*- coding: utf-8 -*-
"""네이버 뉴스 검색 API 수집 (최신순 페이지 넘기기) + 중복 제거."""
import html
import re
import time
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

import requests

from .config import PREFILTER_EXCLUDE, SECTIONS, WISET_SECTION
from .window import KST

API = "https://openapi.naver.com/v1/search/news.json"
PAGE = 100
MAX_START = 1000  # 네이버 API 상한

SOURCES = {
    "chosun.com": "조선일보", "biz.chosun.com": "조선비즈", "it.chosun.com": "IT조선", "joongang.co.kr": "중앙일보",
    "donga.com": "동아일보", "dongascience.com": "동아사이언스", "hani.co.kr": "한겨레", "khan.co.kr": "경향신문",
    "yna.co.kr": "연합뉴스", "yonhapnewstv.co.kr": "연합뉴스TV", "newsis.com": "뉴시스", "news1.kr": "뉴스1",
    "newspim.com": "뉴스핌", "mt.co.kr": "머니투데이", "etnews.com": "전자신문", "zdnet.co.kr": "지디넷코리아",
    "dt.co.kr": "디지털타임스", "hellodd.com": "대덕넷", "kbs.co.kr": "KBS", "imbc.com": "MBC", "sbs.co.kr": "SBS",
    "ytn.co.kr": "YTN", "science.ytn.co.kr": "YTN사이언스", "jtbc.co.kr": "JTBC", "hankyung.com": "한국경제",
    "mk.co.kr": "매일경제", "sedaily.com": "서울경제", "fnnews.com": "파이낸셜뉴스", "edaily.co.kr": "이데일리",
    "asiae.co.kr": "아시아경제", "heraldcorp.com": "헤럴드경제", "munhwa.com": "문화일보", "kmib.co.kr": "국민일보",
    "seoul.co.kr": "서울신문", "segye.com": "세계일보", "hankookilbo.com": "한국일보", "inews24.com": "아이뉴스24",
    "womennews.co.kr": "여성신문", "kyosu.net": "교수신문", "veritas-a.com": "베리타스알파", "ajunews.com": "아주경제",
    "etoday.co.kr": "이투데이", "bloter.net": "블로터", "ddaily.co.kr": "디지털데일리", "dailian.co.kr": "데일리안",
    "naeil.com": "내일신문", "kookje.co.kr": "국제신문", "busan.com": "부산일보", "daejonilbo.com": "대전일보",
    "cctoday.co.kr": "충청투데이", "nocutnews.co.kr": "노컷뉴스", "ohmynews.com": "오마이뉴스", "pressian.com": "프레시안",
    "korea.kr": "정책브리핑", "koreaherald.com": "코리아헤럴드", "koreatimes.co.kr": "코리아타임스",
    "economist.co.kr": "이코노미스트", "sisajournal.com": "시사저널", "dnews.co.kr": "대한경제",
    "electimes.com": "전기신문", "kukinews.com": "쿠키뉴스", "wowtv.co.kr": "한국경제TV", "bbsi.co.kr": "BBS",
    "unn.net": "한국대학신문", "edupress.kr": "에듀프레스", "ebn.co.kr": "EBN", "thebell.co.kr": "더벨",
    "digitaltoday.co.kr": "디지털투데이", "the-pr.co.kr": "더피알", "fntimes.com": "한국금융신문",
    "newstomato.com": "뉴스토마토", "kpinews.kr": "KPI뉴스", "ekn.kr": "에너지경제", "sciencetimes.co.kr": "사이언스타임즈",
    "kizmom.co.kr": "키즈맘", "mbn.co.kr": "MBN", "ichannela.com": "채널A", "tvchosun.com": "TV조선",
    "sisaweek.com": "시사위크", "yakup.com": "약업신문", "kpanews.co.kr": "약사공론", "asiatoday.co.kr": "아시아투데이",
    "businesspost.co.kr": "비즈니스포스트", "newsworks.co.kr": "뉴스웍스", "metroseoul.co.kr": "메트로신문",
    "lecturernews.com": "한국강사신문", "newsworker.co.kr": "뉴스워커", "pinpointnews.co.kr": "핀포인트뉴스",
    "womaneconomy.co.kr": "여성경제신문", "e-science.co.kr": "e사이언스", "biz.newdaily.co.kr": "뉴데일리경제",
    "newdaily.co.kr": "뉴데일리", "news.tf.co.kr": "더팩트", "breaknews.com": "브레이크뉴스", "dkilbo.com": "대경일보",
    "eroun.net": "이로운넷", "kyeonggi.com": "경기일보", "ksilbo.co.kr": "경상일보", "yeongnam.com": "영남일보",
    "imaeil.com": "매일신문", "kwnews.co.kr": "강원일보", "joongdo.co.kr": "중도일보", "ggilbo.com": "금강일보",
    "hankooki.com": "한국일보", "nongmin.com": "농민신문", "medigatenews.com": "메디게이트뉴스",
    "dailymedi.com": "데일리메디", "e-patentnews.com": "특허뉴스", "kyosu.net": "교수신문", "dnews.co.kr": "대한경제",
}
# 이 표에 있는 언론사만 후보로 둔다 (WISET 섹션 제외). 빠진 주요 매체는 여기에 추가.
KNOWN_SOURCES = set(SOURCES.values())


def source_of(url):
    host = (urlsplit(url).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    best = ""
    for dom, name in SOURCES.items():  # 가장 긴 도메인 우선 (biz.chosun.com > chosun.com)
        if (host == dom or host.endswith("." + dom)) and len(dom) > len(best):
            best = dom
    return SOURCES[best] if best else host


def clean(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def norm_title(t):
    t = re.sub(r"\[[^\]]*\]|\([^)]*\)", "", t)  # [단독] (종합) 등 제거
    return re.sub(r"[\W_]+", "", t).lower()[:40]


def norm_link(u):
    p = urlsplit(u)
    return ((p.hostname or "").removeprefix("www.") + p.path.rstrip("/") + ("?" + p.query if p.query else "")).lower()


class NaverClient:
    def __init__(self, client_id, client_secret, session=None, sleep=0.12):
        self.s = session or requests.Session()
        self.h = {"X-Naver-Client-Id": client_id, "X-Naver-Client-Secret": client_secret}
        self.sleep = sleep
        self.calls = 0
        self.warnings = []

    def _get(self, params):
        for attempt in range(4):
            self.calls += 1
            r = self.s.get(API, headers=self.h, params=params, timeout=15)
            if r.status_code == 200:
                time.sleep(self.sleep)
                return r.json()
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(1.5 * (attempt + 1))
                continue
            raise RuntimeError(f"네이버 API 오류 {r.status_code}: {r.text[:200]}")
        raise RuntimeError("네이버 API 재시도 초과")

    def search_window(self, keyword, start, end):
        """keyword로 [start, end) 사이 기사를 최신순으로 전부 가져온다."""
        out = []
        pos = 1
        while pos <= MAX_START:
            data = self._get({"query": keyword, "display": PAGE, "start": pos, "sort": "date"})
            items = data.get("items", [])
            reached_start = False
            for it in items:
                try:
                    pub = parsedate_to_datetime(it["pubDate"]).astimezone(KST)
                except (KeyError, TypeError, ValueError):
                    continue
                if pub < start:
                    reached_start = True
                    break
                if pub >= end:
                    continue
                link = it.get("originallink") or it.get("link", "")
                out.append({
                    "title": clean(it.get("title")),
                    "desc": clean(it.get("description")),
                    "link": link,
                    "naver_link": it.get("link", ""),
                    "source": source_of(link),
                    "pub": pub.isoformat(timespec="minutes"),
                    "keyword": keyword,
                })
            if reached_start or len(items) < PAGE:
                break
            pos += PAGE
        else:
            self.warnings.append(f"'{keyword}': API 상한(1,000건)에 도달해 기간 앞부분 일부가 빠졌을 수 있음")
        return out


def keyword_in_text(a):
    """검색어의 모든 단어가 제목이나 설명문에 실제로 있는지 (네이버는 본문만 맞아도 검색됨)."""
    text = (a["title"] + " " + a["desc"]).lower()
    return all(t.lower() in text for t in a["keyword"].split())


def collect(client, start, end, log=print):
    """섹션 > 소주제 > 기사 목록. 중복은 앞선 섹션/소주제에 배정."""
    seen_links, seen_titles = set(), set()
    result = {}
    stats = {"raw": 0, "dup": 0, "offtopic": 0, "minor": 0, "prefiltered": 0}
    for section, subs in SECTIONS.items():
        result[section] = {}
        for sub, keywords in subs.items():
            arts = []
            for kw in keywords:
                found = client.search_window(kw, start, end)
                stats["raw"] += len(found)
                log(f"  [{section} > {sub}] '{kw}': {len(found)}건")
                for a in found:
                    if section != WISET_SECTION:
                        if not keyword_in_text(a):
                            stats["offtopic"] += 1
                            continue
                        if a["source"] not in KNOWN_SOURCES:
                            stats["minor"] += 1
                            continue
                    lk, tk = norm_link(a["link"]), norm_title(a["title"])
                    if lk in seen_links or (tk and tk in seen_titles):
                        stats["dup"] += 1
                        continue
                    seen_links.add(lk)
                    if tk:
                        seen_titles.add(tk)
                    if section != WISET_SECTION and any(x in a["title"] for x in PREFILTER_EXCLUDE):
                        stats["prefiltered"] += 1
                        continue
                    arts.append({**a, "section": section, "sub": sub})
            arts.sort(key=lambda a: a["pub"], reverse=True)
            result[section][sub] = arts
    stats["kept"] = sum(len(v) for subs in result.values() for v in subs.values())
    stats["calls"] = client.calls
    return result, stats
