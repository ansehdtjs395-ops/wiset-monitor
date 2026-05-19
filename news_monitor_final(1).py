# -*- coding: utf-8 -*-
"""
=====================================
 언론 모니터링 자동화 스크립트 (최종 AI버전)
 - 섹션 > 소주제 구조
 - Claude AI: 기사 요약 + 중요도 + 정확한 선별
 - 네이버 뉴스 API (전날+당일, 관련도순)
 - 결과를 HTML 파일로 저장 (바탕화면)
=====================================
"""

import requests
import re
import urllib3
import json
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
import time
import os

urllib3.disable_warnings()

# =============================================
#  ★ 설정 영역
# =============================================

NAVER_CLIENT_ID     = "여기에_Client_ID_입력"
NAVER_CLIENT_SECRET = "여기에_Client_Secret_입력"
CLAUDE_API_KEY      = "여기에_sk-ant-키_입력"

SAVE_FOLDER = os.path.join(os.path.expanduser("~"), "Desktop", "언론모니터링")

NAVER_FETCH_COUNT = 20
NAVER_SHOW_COUNT  = 5

# =============================================
#  ★ 섹션 > 소주제 > 키워드 구조
# =============================================

SECTIONS = {

    "WISET": {
        "WISET": ["WISET", "여성과학기술인지원센터"],
    },

    "정부정책동향": {
        "과학기술정보통신부": [
            "과학기술정보통신부", "과기부", "과기정통부",
            "배경훈 장관", "구혁채 차관", "과방위",
        ],
        "여성가족부": [
            "여성가족부",
        ],
        "고용노동부": [
            "고용노동부",
        ],
        "교육부": [
            "교육부 과학", "교육부 이공계",
        ],
        "중소벤처기업부": [
            "중소벤처기업부 과학", "중소벤처기업부 여성",
        ],
        "정책브리핑": [
            "정책브리핑 과학", "정책브리핑 여성",
        ],
    },

    "유관기관동향": {
        "정부출연연구기관": [
            "KIST", "ETRI", "STEPI", "IBS", "KISTEP", "KIRD",
            "한국기계연구원", "한국전기연구원", "한국뇌연구원",
            "한국원자력의학원", "한국화학연구원", "한국생명공학연구원",
            "한국항공우주연구원", "한국에너지기술연구원",
            "한국전자통신연구원", "출연연",
        ],
        "4대 과학기술원": [
            "KAIST", "GIST", "DGIST", "UNIST",
            "한국과학기술원", "광주과학기술원",
            "대구경북과학기술원", "울산과학기술원",
        ],
        "한국과학창의재단": [
            "과학창의재단", "한국과학창의재단", "창의재단",
        ],
        "과학기술한림원": [
            "과학기술한림원", "한림원",
        ],
        "과총·단체": [
            "과총", "여과총", "한국과학기술단체총연합회",
            "대한여성과학기술인회", "여성과학기술단체총연합회",
            "국가과학기술자문회의",
        ],
        "기타 유관기관": [
            "NST", "한국연구재단", "정보통신기획평가원",
            "국립과학관", "고등과학원", "IITP",
            "과학기술정보통신부 산하", "과기정통부 산하",
        ],
    },

    "여성과학기술인": {
        "여성 과학자·연구자": [
            "여성 과학자", "여성 연구자", "여성 공학자",
            "여성 엔지니어", "여성 원장",
        ],
        "이공계 여성 현황·정책": [
            "이공계 여성", "여성 이공계", "여성 교수 과학",
            "여성할당 과학", "여성 임원 기술", "유리천장 과학",
        ],
        "경력단절·젠더": [
            "경력단절 연구", "경단녀 과학", "젠더혁신",
        ],
    },

    "참고보도": {
        "인재·채용": [
            "이공계", "과학기술인재", "IT인재", "SW인재", "미래인재 과학",
        ],
        "일·가정양립": [
            "일가정양립 연구", "육아 과학기술", "출산 연구자",
        ],
        "다양성·포용": [
            "다양성 과학", "포용성 이공계",
        ],
        "주요 과학매체": [
            "대덕넷", "동아사이언스", "YTN사이언스", "KISTEP 뉴스트렌드",
        ],
    },

    "기고칼럼": {
        "과학기술 칼럼·기고": [
            "칼럼 과학기술", "기고 과학기술", "기고 이공계",
            "칼럼 이공계", "기고 디지털",
        ],
        "사설·시평": [
            "사설 과학", "과기계는 지금", "과학의 달인",
        ],
    },
}

# =============================================
#  전날 + 당일 여부 확인
# =============================================

def is_recent(pub_date_str):
    try:
        pub_date  = parsedate_to_datetime(pub_date_str).date()
        today     = datetime.now().date()
        yesterday = today - timedelta(days=1)
        return pub_date in (today, yesterday)
    except Exception:
        return True

# =============================================
#  언론사명 추출
# =============================================

def extract_source(url):
    domain_map = {
        "chosun": "조선", "joongang": "중앙", "donga": "동아",
        "hani": "한겨레", "khan": "경향", "yonhap": "연합뉴스",
        "yna": "연합뉴스", "newsis": "뉴시스", "newspim": "뉴스핌",
        "mt": "머니투데이", "etnews": "전자신문", "zdnet": "ZDNet",
        "dt": "디지털타임스", "hellodd": "대덕넷",
        "dongascience": "동아사이언스", "sciencetimes": "사이언스타임즈",
        "kbs": "KBS", "mbc": "MBC", "sbs": "SBS",
        "ytn": "YTN", "jtbc": "JTBC", "hankyung": "한국경제",
        "mk": "매일경제", "sedaily": "서울경제",
        "fnnews": "파이낸셜뉴스", "bloter": "블로터",
        "idaily": "이데일리", "asiae": "아시아경제",
        "heraldcorp": "헤럴드", "munhwa": "문화", "kukmin": "국민",
    }
    url_lower = url.lower()
    for key, name in domain_map.items():
        if key in url_lower:
            return name
    return ""

# =============================================
#  네이버 뉴스 수집
# =============================================

def fetch_naver_news(keyword):
    articles = []
    try:
        response = requests.get(
            "https://openapi.naver.com/v1/search/news.json",
            headers={
                "X-Naver-Client-Id":     NAVER_CLIENT_ID,
                "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
            },
            params={"query": keyword, "display": NAVER_FETCH_COUNT, "sort": "sim"},
            timeout=10, verify=False
        )
        response.raise_for_status()
        for item in response.json().get("items", []):
            if not is_recent(item.get("pubDate", "")):
                continue
            title  = re.sub(r"<[^>]+>", "", item.get("title", "")).strip()
            desc   = re.sub(r"<[^>]+>", "", item.get("description", "")).strip()
            link   = item.get("originallink") or item.get("link", "")
            source = extract_source(link)
            articles.append({
                "title": title, "desc": desc,
                "link": link, "source": source
            })
            if len(articles) >= NAVER_SHOW_COUNT:
                break
    except Exception as e:
        print(f"    오류 [{keyword}]: {e}")
    return articles

# =============================================
#  중복 제거
# =============================================

def deduplicate(articles, seen_global):
    unique = []
    for art in articles:
        key = re.sub(r"[\s\W]", "", art["title"]).lower()[:30]
        if key and key not in seen_global:
            seen_global.add(key)
            unique.append(art)
    return unique

# =============================================
#  Claude AI - 선별 + 요약 + 중요도
# =============================================

def ai_analyze(articles, section_name, subsection_name):
    if not articles:
        return []

    articles_json = json.dumps(
        [{"id": i, "title": a["title"], "desc": a["desc"]}
         for i, a in enumerate(articles)],
        ensure_ascii=False
    )

    # 기고칼럼 섹션은 작성자 추출 포함
    is_column = "칼럼" in subsection_name or "기고" in subsection_name or "사설" in subsection_name

    if is_column:
        json_format = """[
  {
    "id": 0,
    "include": true,
    "summary": "30자 이내 한 줄 요약",
    "importance": "★★★",
    "author": "홍길동 KAIST 교수"
  }
]

author 추출 방법:
- 제목이나 설명에서 작성자 이름·소속을 찾아 "이름 소속직책" 형식으로 작성
- 작성자를 알 수 없으면 빈 문자열 "" 로 두세요"""
    else:
        json_format = """[
  {
    "id": 0,
    "include": true,
    "summary": "30자 이내 한 줄 요약",
    "importance": "★★★"
  }
]"""

    prompt = f"""당신은 한국여성과학기술인육성재단(WISET) PR팀 언론모니터링 담당자입니다.
WISET은 여성 과학기술인 육성, 이공계 여성 경력 지원, 과학기술 정책 관련 업무를 합니다.

섹션: {section_name} > {subsection_name}

=== 반드시 제외할 기사 유형 ===
- 범죄·사건·사고 뉴스 (마약, 폭행, 사기, 교통사고, 추락 등)
- 연예·스포츠·패션·뷰티 뉴스
- 의료·성형외과·병원 관련 뉴스 (과학기술 정책과 무관한 것)
- 부동산·금융·주식 뉴스
- 일반 정치 뉴스 (과학기술 정책과 직접 무관한 것)
- 원장·교수·박사가 등장하더라도 과학기술기관 소속이 아닌 경우
- 제목에 과학기술 키워드가 있어도 실제 내용이 전혀 무관한 경우

=== 포함할 기사 유형 ===
- 과기부·여성가족부·고용부 등 정부의 과학기술·여성·인재 정책 발표
- 출연연·4대과기원·과총·여과총 등 과학기술 기관 공식 활동
- 여성 과학자·연구자·공학자 관련 기사 (실명·소속 없어도 무방, 이공계 여성 관련이면 포함)
- 이공계 여성 현황, 경력단절, 젠더혁신 관련 정책·연구
- 과학기술 분야 오피니언·칼럼·기고·사설 (태그 없어도 내용이 과학기술 관련이면 포함)
- WISET 직접 관련 행사·프로그램·기관장 기고

기사 목록:
{articles_json}

반드시 아래 JSON 형식으로만 응답하세요:
{json_format}

중요도 기준:
★★★ WISET 직접 관련 또는 즉시 대응 필요 (예: WISET 언급, 여성과학기술인 정책, 기관장 기고)
★★☆ 업무 참고 필요 (예: 과기부 정책, 유관기관 동향, 여성 연구자 성과)
★☆☆ 동향 파악용 (예: 이공계 일반 동향, 참고 기사)"""

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key":         CLAUDE_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type":      "application/json",
            },
            json={
                "model":      "claude-haiku-4-5-20251001",
                "max_tokens": 1000,
                "messages":   [{"role": "user", "content": prompt}],
            },
            timeout=30, verify=False
        )
        resp.raise_for_status()
        text    = resp.json()["content"][0]["text"].strip()
        match   = re.search(r'\[.*\]', text, re.DOTALL)
        results = json.loads(match.group())

        filtered = []
        for r in results:
            if r.get("include"):
                art = articles[r["id"]].copy()
                art["summary"]    = r.get("summary", "")
                art["importance"] = r.get("importance", "★☆☆")
                art["author"]     = r.get("author", "")
                filtered.append(art)

        print(f"      AI: {len(articles)}건 → {len(filtered)}건")
        return filtered

    except Exception as e:
        print(f"      AI 오류: {e}")
        for art in articles:
            art["summary"]    = ""
            art["importance"] = "★☆☆"
        return articles

# =============================================
#  HTML 생성
# =============================================

SECTION_COLORS = {
    "WISET":       "#1a3c8f",
    "정부정책동향": "#1a3c8f",
    "유관기관동향": "#1e7e34",
    "여성과학기술인": "#7b1fa2",
    "참고보도":    "#e65100",
    "기고칼럼":    "#283593",
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
    total    = sum(
        len(arts)
        for subs in section_results.values()
        for arts in subs.values()
    )

    body = ""
    for section, subsections in section_results.items():
        # 섹션 전체 기사 수
        section_total = sum(len(v) for v in subsections.values())
        if section_total == 0:
            continue

        color = SECTION_COLORS.get(section, "#333")

        # 소주제 HTML
        subs_html = ""
        for sub, arts in subsections.items():
            if not arts:
                continue

            items_html = ""
            for art in arts:
                src      = f"({art['source']})" if art.get("source") else ""
                imp      = art.get("importance", "")
                summary  = art.get("summary", "")
                ic       = importance_color(imp)
                imp_span = f'<span style="color:{ic};font-size:12px;margin-left:6px;font-weight:600;">{imp}</span>' if imp else ""
                sum_div  = f'<div style="font-size:12px;color:#888;padding:1px 0 4px 14px;">→ {summary}</div>' if summary else ""

                items_html += f"""
                <tr>
                  <td style="padding:4px 0 1px;">
                    <div style="font-size:14px;line-height:1.8;color:#222;">
                      ㆍ{src}
                      <a href="{art['link']}" target="_blank"
                         style="color:#1a3c8f;text-decoration:none;">{art['title']}</a>
                      {imp_span}
                    </div>
                    {sum_div}
                  </td>
                </tr>"""

            subs_html += f"""
            <tr>
              <td style="padding:12px 0 4px 0;">
                <div style="display:inline-block;font-size:13px;font-weight:600;
                            color:{color};background:{color}15;
                            padding:3px 12px;border-radius:20px;margin-bottom:6px;">
                  ▸ {sub}
                </div>
                <table width="100%" cellpadding="0" cellspacing="0" style="padding-left:4px;">
                  {items_html}
                </table>
              </td>
            </tr>"""

        body += f"""
        <tr>
          <td style="padding:24px 0 0;">
            <!-- 섹션 헤더 -->
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td style="padding:10px 16px;background:{color};border-radius:4px 4px 0 0;">
                  <span style="font-size:16px;font-weight:800;color:#fff;">◆ {section}</span>
                  <span style="font-size:12px;color:rgba(255,255,255,0.7);
                               margin-left:10px;">{section_total}건</span>
                </td>
              </tr>
              <tr>
                <td style="padding:8px 16px 16px;border:1px solid #e8e8e8;
                           border-top:none;border-radius:0 0 4px 4px;">
                  <table width="100%" cellpadding="0" cellspacing="0">
                    {subs_html}
                  </table>
                </td>
              </tr>
            </table>
          </td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <title>주요 언론보도 {now.strftime('%Y-%m-%d')}</title>
  <style>
    body {{ margin:0;padding:0;background:#f0f2f5;
           font-family:'Apple SD Gothic Neo','Malgun Gothic',Arial,sans-serif; }}
    a:hover {{ text-decoration:underline !important; }}
  </style>
</head>
<body>
  <table width="100%" cellpadding="0" cellspacing="0" style="padding:30px 0;">
    <tr><td align="center">
    <table width="740" cellpadding="0" cellspacing="0"
           style="background:#fff;border-radius:8px;
                  box-shadow:0 2px 20px rgba(0,0,0,0.10);">

      <!-- 헤더 -->
      <tr>
        <td style="padding:32px 40px 20px;border-bottom:3px solid #1a3c8f;">
          <p style="margin:0 0 6px;font-size:24px;font-weight:800;
                    color:#1a3c8f;letter-spacing:-0.5px;">주요 언론보도</p>
          <p style="margin:0;font-size:14px;color:#666;">{date_str}</p>
        </td>
      </tr>

      <!-- 중요도 안내 -->
      <tr>
        <td style="padding:10px 40px;background:#fafafa;border-bottom:1px solid #eee;">
          <span style="font-size:12px;color:#c0392b;font-weight:600;">★★★ WISET 직접 관련</span>
          <span style="font-size:12px;color:#e67e22;font-weight:600;margin-left:20px;">★★☆ 업무 참고</span>
          <span style="font-size:12px;color:#95a5a6;font-weight:600;margin-left:20px;">★☆☆ 동향 파악</span>
        </td>
      </tr>

      <!-- 본문 -->
      <tr>
        <td style="padding:0 40px 32px;">
          <table width="100%" cellpadding="0" cellspacing="0">
            {body}
          </table>
        </td>
      </tr>

      <!-- 푸터 -->
      <tr>
        <td style="padding:14px 40px;background:#f8f9fb;
                   border-top:1px solid #e8e8e8;border-radius:0 0 8px 8px;">
          <p style="margin:0;font-size:12px;color:#bbb;">
            총 {total}건 · {period} 기준 · {now.strftime("%H:%M")} 자동 수집 · WISET 언론모니터링
          </p>
        </td>
      </tr>

    </table>
    </td></tr>
  </table>
</body>
</html>"""

# =============================================
#  HTML 저장
# =============================================

def save_html(html_body):
    os.makedirs(SAVE_FOLDER, exist_ok=True)
    filename = f"언론보도_{datetime.now().strftime('%Y%m%d')}.html"
    filepath = os.path.join(SAVE_FOLDER, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_body)
    print(f"  저장 완료 -> {filepath}")
    return filepath

# =============================================
#  메인 실행
# =============================================

def main():
    print("=" * 55)
    print(f"  언론 모니터링 시작 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 55)

    seen_global    = set()
    section_results = {}

    for section, subsections in SECTIONS.items():
        print(f"\n▶ {section}")
        section_results[section] = {}

        for sub, keywords in subsections.items():
            print(f"  · {sub}")
            sub_articles = []

            for keyword in keywords:
                arts   = fetch_naver_news(keyword)
                unique = deduplicate(arts, seen_global)
                if unique:
                    print(f"    {keyword} → {len(unique)}건")
                sub_articles.extend(unique)
                time.sleep(0.2)

            # AI 선별 + 요약 + 중요도
            if sub_articles:
                sub_articles = ai_analyze(sub_articles, section, sub)

            section_results[section][sub] = sub_articles

        sec_total = sum(len(v) for v in section_results[section].values())
        print(f"  소계: {sec_total}건")

    total = sum(
        len(arts)
        for subs in section_results.values()
        for arts in subs.values()
    )
    print(f"\n수집 완료 -- 총 {total}건")

    if total == 0:
        print("  수집된 기사가 없습니다.")
        return

    print("\nHTML 저장 중...")
    filepath = save_html(build_html(section_results))
    os.startfile(filepath)

    print("\n" + "=" * 55)
    print(f"  완료 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 55)

if __name__ == "__main__":
    main()
