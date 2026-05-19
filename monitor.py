# -*- coding: utf-8 -*-
import requests
import re
import json
import urllib3
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
import time
import os

urllib3.disable_warnings()

NAVER_CLIENT_ID     = os.environ["NAVER_CLIENT_ID"]
NAVER_CLIENT_SECRET = os.environ["NAVER_CLIENT_SECRET"]
CLAUDE_API_KEY      = os.environ["CLAUDE_API_KEY"]

NAVER_FETCH_COUNT = 20
NAVER_SHOW_COUNT  = 5

SECTIONS = {
    "WISET": {
        "WISET": ["WISET", "여성과학기술인지원센터"],
    },
    "정부정책동향": {
        "과학기술정보통신부": ["과학기술정보통신부", "과기부", "과기정통부", "배경훈 장관", "구혁채 차관", "과방위"],
        "여성가족부": ["여성가족부"],
        "고용노동부": ["고용노동부"],
        "교육부": ["교육부 과학", "교육부 이공계"],
        "중소벤처기업부": ["중소벤처기업부 과학", "중소벤처기업부 여성"],
        "정책브리핑": ["정책브리핑 과학", "정책브리핑 여성"],
    },
    "유관기관동향": {
        "정부출연연구기관": ["KIST", "ETRI", "STEPI", "IBS", "KISTEP", "KIRD", "한국기계연구원", "한국전기연구원", "한국뇌연구원", "한국원자력의학원", "한국화학연구원", "한국생명공학연구원", "한국항공우주연구원", "출연연"],
        "4대 과학기술원": ["KAIST", "GIST", "DGIST", "UNIST", "한국과학기술원", "광주과학기술원", "대구경북과학기술원", "울산과학기술원"],
        "한국과학창의재단": ["과학창의재단", "한국과학창의재단", "창의재단"],
        "과학기술한림원": ["과학기술한림원", "한림원"],
        "과총·단체": ["과총", "여과총", "한국과학기술단체총연합회", "대한여성과학기술인회", "여성과학기술단체총연합회", "국가과학기술자문회의"],
        "기타 유관기관": ["NST", "한국연구재단", "정보통신기획평가원", "국립과학관", "고등과학원", "IITP", "과학기술정보통신부 산하"],
    },
    "여성과학기술인": {
        "여성 과학자·연구자": ["여성 과학자", "여성 연구자", "여성 공학자", "여성 엔지니어", "여성 원장"],
        "이공계 여성 현황·정책": ["이공계 여성", "여성 이공계", "여성 교수 과학", "여성할당 과학", "여성 임원 기술", "유리천장 과학"],
        "경력단절·젠더": ["경력단절 연구", "경단녀 과학", "젠더혁신"],
    },
    "참고보도": {
        "인재·채용": ["이공계", "과학기술인재", "IT인재", "SW인재", "미래인재 과학"],
        "일·가정양립": ["일가정양립 연구", "육아 과학기술", "출산 연구자"],
        "다양성·포용": ["다양성 과학", "포용성 이공계"],
        "주요 과학매체": ["대덕넷", "동아사이언스", "YTN사이언스", "KISTEP 뉴스트렌드"],
    },
    "기고칼럼": {
        "과학기술 칼럼·기고": ["칼럼 과학기술", "기고 과학기술", "기고 이공계", "칼럼 이공계", "기고 디지털"],
        "사설·시평": ["사설 과학", "과기계는 지금", "과학의 달인"],
    },
}

def is_recent(pub_date_str):
    try:
        pub_date  = parsedate_to_datetime(pub_date_str).date()
        today     = datetime.now().date()
        yesterday = today - timedelta(days=1)
        return pub_date in (today, yesterday)
    except Exception:
        return True

def extract_source(url):
    domain_map = {
        "chosun": "조선", "joongang": "중앙", "donga": "동아",
        "hani": "한겨레", "khan": "경향", "yonhap": "연합뉴스",
        "yna": "연합뉴스", "newsis": "뉴시스", "newspim": "뉴스핌",
        "mt": "머니투데이", "etnews": "전자신문", "zdnet": "ZDNet",
        "dt": "디지털타임스", "hellodd": "대덕넷",
        "dongascience": "동아사이언스", "kbs": "KBS", "mbc": "MBC",
        "sbs": "SBS", "ytn": "YTN", "jtbc": "JTBC",
        "hankyung": "한국경제", "mk": "매일경제", "sedaily": "서울경제",
        "fnnews": "파이낸셜뉴스", "idaily": "이데일리",
        "asiae": "아시아경제", "heraldcorp": "헤럴드",
        "munhwa": "문화", "kukmin": "국민",
    }
    url_lower = url.lower()
    for key, name in domain_map.items():
        if key in url_lower:
            return name
    return ""

def fetch_naver_news(keyword):
    articles = []
    try:
        response = requests.get(
            "https://openapi.naver.com/v1/search/news.json",
            headers={"X-Naver-Client-Id": NAVER_CLIENT_ID, "X-Naver-Client-Secret": NAVER_CLIENT_SECRET},
            params={"query": keyword, "display": NAVER_FETCH_COUNT, "sort": "sim"},
            timeout=10
        )
        response.raise_for_status()
        for item in response.json().get("items", []):
            if not is_recent(item.get("pubDate", "")):
                continue
            title  = re.sub(r"<[^>]+>", "", item.get("title", "")).strip()
            desc   = re.sub(r"<[^>]+>", "", item.get("description", "")).strip()
            link   = item.get("originallink") or item.get("link", "")
            source = extract_source(link)
            articles.append({"title": title, "desc": desc, "link": link, "source": source})
            if len(articles) >= NAVER_SHOW_COUNT:
                break
    except Exception as e:
        print(f"    오류 [{keyword}]: {e}")
    return articles

def deduplicate(articles, seen_global):
    unique = []
    for art in articles:
        key = re.sub(r"[\s\W]", "", art["title"]).lower()[:30]
        if key and key not in seen_global:
            seen_global.add(key)
            unique.append(art)
    return unique

def ai_analyze_section(articles, section_name, subsections):
    """섹션 전체를 한 번에 AI 분석 - 소주제 분류 포함"""
    if not articles:
        return {sub: [] for sub in subsections}

    is_column = section_name == "기고칼럼"
    sub_list  = list(subsections.keys())

    articles_json = json.dumps(
        [{"id": i, "title": a["title"], "desc": a["desc"]} for i, a in enumerate(articles)],
        ensure_ascii=False
    )

    if is_column:
        json_example = (
            '[\n'
            '  {\n'
            '    "id": 0,\n'
            '    "include": true,\n'
            f'    "subsection": "{sub_list[0]}",\n'
            '    "summary": "30자 이내 한 줄 요약",\n'
            '    "importance": "★★★",\n'
            '    "author": "홍길동 KAIST 교수"\n'
            '  }\n'
            ']'
        )
    else:
        json_example = (
            '[\n'
            '  {\n'
            '    "id": 0,\n'
            '    "include": true,\n'
            f'    "subsection": "{sub_list[0]}",\n'
            '    "summary": "30자 이내 한 줄 요약",\n'
            '    "importance": "★★★"\n'
            '  }\n'
            ']'
        )

    prompt = f"""당신은 한국여성과학기술인육성재단(WISET) PR팀 언론모니터링 담당자입니다.

섹션: {section_name}
소주제 목록: {json.dumps(sub_list, ensure_ascii=False)}

=== 반드시 제외할 기사 ===
- 범죄·사건·사고 (마약, 폭행, 사기, 교통사고 등)
- 연예·스포츠·패션·뷰티
- 의료·성형외과 (과학기술 정책과 무관)
- 부동산·금융·주식
- 원장·교수가 등장해도 과학기술기관 소속이 아니면 제외

=== 포함할 기사 ===
- 과기부·여성가족부 등 정부의 과학기술·여성·인재 정책
- 출연연·4대과기원·과총 등 과학기술 기관 활동
- 여성 과학자·연구자 관련 기사 (이공계 여성 관련이면 포함)
- 과학기술 분야 오피니언·칼럼·기고·사설

기사 목록:
{articles_json}

각 기사를 분석해서 반드시 아래 JSON 형식으로만 응답하세요:
{json_example}

subsection은 반드시 소주제 목록 중 하나로만 지정하세요.
중요도: ★★★ WISET 직접 관련 / ★★☆ 업무 참고 / ★☆☆ 동향 파악"""

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": CLAUDE_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": "claude-haiku-4-5-20251001", "max_tokens": 2000, "messages": [{"role": "user", "content": prompt}]},
            timeout=60
        )
        resp.raise_for_status()
        text    = resp.json()["content"][0]["text"].strip()
        match   = re.search(r'\[.*\]', text, re.DOTALL)
        results = json.loads(match.group())

        # 소주제별로 분류
        sub_results = {sub: [] for sub in sub_list}
        for r in results:
            if not r.get("include"):
                continue
            art = articles[r["id"]].copy()
            art["summary"]    = r.get("summary", "")
            art["importance"] = r.get("importance", "★☆☆")
            art["author"]     = r.get("author", "")
            sub = r.get("subsection", sub_list[0])
            if sub not in sub_results:
                sub = sub_list[0]
            sub_results[sub].append(art)

        total = sum(len(v) for v in sub_results.values())
        print(f"    AI: {len(articles)}건 → {total}건 선별")
        return sub_results

    except Exception as e:
        print(f"    AI 오류: {e}")
        # 오류시 기존 소주제 분류 유지
        result = {sub: [] for sub in sub_list}
        for art in articles:
            art["summary"] = ""
            art["importance"] = "★☆☆"
            art["author"] = ""
        result[sub_list[0]] = articles
        return result

SECTION_COLORS = {
    "WISET": "#1a3c8f", "정부정책동향": "#1a3c8f",
    "유관기관동향": "#1e7e34", "여성과학기술인": "#7b1fa2",
    "참고보도": "#e65100", "기고칼럼": "#283593",
}

def importance_color(imp):
    if "★★★" in imp: return "#c0392b"
    if "★★"  in imp: return "#e67e22"
    return "#95a5a6"

def build_html(section_results):
    now      = datetime.now()
    weekdays = ["월", "화", "수", "목", "금", "토", "일"]
    date_str = f"{now.year}년 {now.month}월 {now.day}일 {weekdays[now.weekday()]}요일"
    yesterday = now - timedelta(days=1)
    period   = f"{yesterday.month}월 {yesterday.day}일 ~ {now.month}월 {now.day}일"
    total    = sum(len(arts) for subs in section_results.values() for arts in subs.values())

    body = ""
    for section, subsections in section_results.items():
        section_total = sum(len(v) for v in subsections.values())
        if section_total == 0:
            continue
        color = SECTION_COLORS.get(section, "#333")
        subs_html = ""
        for sub, arts in subsections.items():
            if not arts:
                continue
            items_html = ""
            for art in arts:
                src        = f"({art['source']})" if art.get("source") else ""
                imp        = art.get("importance", "")
                summary    = art.get("summary", "")
                author     = art.get("author", "")
                ic         = importance_color(imp)
                imp_span   = f'<span style="color:{ic};font-size:12px;margin-left:6px;font-weight:600;">{imp}</span>' if imp else ""
                author_div = f'<div style="font-size:12px;color:#e67e22;padding:1px 0 1px 14px;">✍️ {author}</div>' if author else ""
                sum_div    = f'<div style="font-size:12px;color:#888;padding:1px 0 4px 14px;">→ {summary}</div>' if summary else ""
                items_html += f"""<tr><td style="padding:4px 0 1px;">
                    <div style="font-size:14px;line-height:1.8;color:#222;">ㆍ{src}
                    <a href="{art['link']}" target="_blank" style="color:#1a3c8f;text-decoration:none;">{art['title']}</a>{imp_span}</div>
                    {author_div}{sum_div}</td></tr>"""
            subs_html += f"""<tr><td style="padding:12px 0 4px 0;">
                <div style="display:inline-block;font-size:13px;font-weight:600;color:{color};background:{color}15;padding:3px 12px;border-radius:20px;margin-bottom:6px;">▸ {sub}</div>
                <table width="100%" cellpadding="0" cellspacing="0" style="padding-left:4px;">{items_html}</table></td></tr>"""
        body += f"""<tr><td style="padding:24px 0 0;">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr><td style="padding:10px 16px;background:{color};border-radius:4px 4px 0 0;">
                <span style="font-size:16px;font-weight:800;color:#fff;">◆ {section}</span>
                <span style="font-size:12px;color:rgba(255,255,255,0.7);margin-left:10px;">{section_total}건</span>
              </td></tr>
              <tr><td style="padding:8px 16px 16px;border:1px solid #e8e8e8;border-top:none;border-radius:0 0 4px 4px;">
                <table width="100%" cellpadding="0" cellspacing="0">{subs_html}</table>
              </td></tr>
            </table></td></tr>"""

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>주요 언론보도 {now.strftime('%Y-%m-%d')}</title>
<style>body{{margin:0;padding:0;background:#f0f2f5;font-family:'Malgun Gothic',Arial,sans-serif;}}a:hover{{text-decoration:underline!important;}}</style>
</head>
<body>
<table width="100%" cellpadding="0" cellspacing="0" style="padding:30px 0;">
<tr><td align="center">
<table width="740" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:8px;box-shadow:0 2px 20px rgba(0,0,0,0.10);">
<tr><td style="padding:32px 40px 20px;border-bottom:3px solid #1a3c8f;">
  <p style="margin:0 0 6px;font-size:24px;font-weight:800;color:#1a3c8f;">주요 언론보도</p>
  <p style="margin:0;font-size:14px;color:#666;">{date_str}</p>
</td></tr>
<tr><td style="padding:10px 40px;background:#fafafa;border-bottom:1px solid #eee;">
  <span style="font-size:12px;color:#c0392b;font-weight:600;">★★★ WISET 직접 관련</span>
  <span style="font-size:12px;color:#e67e22;font-weight:600;margin-left:20px;">★★☆ 업무 참고</span>
  <span style="font-size:12px;color:#95a5a6;font-weight:600;margin-left:20px;">★☆☆ 동향 파악</span>
</td></tr>
<tr><td style="padding:0 40px 32px;">
  <table width="100%" cellpadding="0" cellspacing="0">{body}</table>
</td></tr>
<tr><td style="padding:14px 40px;background:#f8f9fb;border-top:1px solid #e8e8e8;border-radius:0 0 8px 8px;">
  <p style="margin:0;font-size:12px;color:#bbb;">총 {total}건 · {period} 기준 · {now.strftime("%H:%M")} 자동 수집 · WISET 언론모니터링</p>
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>"""

def main():
    print(f"언론 모니터링 시작 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    seen_global    = set()
    section_results = {}

    for section, subsections in SECTIONS.items():
        print(f"\n▶ {section}")
        # 섹션 전체 기사 수집
        all_articles = []
        for sub, keywords in subsections.items():
            print(f"  · {sub}")
            for keyword in keywords:
                arts   = fetch_naver_news(keyword)
                unique = deduplicate(arts, seen_global)
                if unique:
                    print(f"    {keyword} → {len(unique)}건")
                all_articles.extend(unique)
                time.sleep(0.2)

        # 섹션 전체를 AI에 한 번만 보내서 소주제 분류까지 처리
        print(f"  AI 분석 중... ({len(all_articles)}건)")
        sub_results = ai_analyze_section(all_articles, section, subsections)
        section_results[section] = sub_results

        sec_total = sum(len(v) for v in sub_results.values())
        print(f"  소계: {sec_total}건")

    total = sum(len(arts) for subs in section_results.values() for arts in subs.values())
    print(f"\n수집 완료 -- 총 {total}건")

    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(build_html(section_results))
    print("저장 완료: docs/index.html")

if __name__ == "__main__":
    main()
