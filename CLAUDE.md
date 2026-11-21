# WISET 언론모니터링 자동화 — 작업 규칙

한국여성과학기술인육성재단(WISET) 대외협력홍보팀의 매일 아침 언론모니터링을 자동화한다.
평일 07:30(KST)에 GitHub Actions가 네이버 뉴스를 모으고, Claude가 선별·요약한 리포트를 GitHub Pages에 올린다.

- 저장소: `ansehdtjs395-ops/wiset-monitor` (공개). 로컬 개발 폴더는 `C:\dev\mds`.
- 리포트 주소: https://ansehdtjs395-ops.github.io/wiset-monitor/ (최신). 보관함은 `/archive/`.
- 사용자는 비개발자다. GitHub 웹 설정은 클릭 단위로 안내하고, 오류는 쉬운 말로 원인을 설명한다.

## 절대 지킬 제약
- 회사 네트워크는 SSL 검사와 SMTP가 막혀 있다 → 메일 발송 금지, 회사 PC 로컬 실행에 의존 금지.
- API 키는 코드에 쓰지 않는다. GitHub Secrets에서만 받는다: `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`, `CLAUDE_API_KEY`.
- 저장소가 공개이므로 배포본 PDF·내부 자료·키를 커밋하지 않는다(`.gitignore`에 `*.pdf`, `.env`, `out/`).
- 모든 날짜·시간은 KST. cron은 UTC라서 9시간을 빼서 쓴다(아래 표).

## 실행 시각 (cron 환산)
| KST | UTC | cron |
|---|---|---|
| 월~금 07:30 | 일~목 22:30 | `30 22 * * 0-4` |
| 월~금 08:30 (예비) | 일~목 23:30 | `30 23 * * 0-4` |
| 월~금 09:30 (예비) | 월~금 00:30 | `30 0 * * 1-5` |

- GitHub 예약 실행은 몇 시간씩 늦어질 수 있다(실측: 07:30 예약이 12:38에 실행됨). 그래서 예비 시각을 두고, 선택 사항으로 cron-job.org가 07:30에 `workflow_dispatch`를 호출한다.
- 같은 날 두 번째 실행은 `오늘 이미 실행됨`으로 바로 끝난다(`window.compute_window`).

## 수집 기간 규칙 (`monitor/window.py`)
- 기간은 `state/last_success.json`(마지막 성공 시각)부터 이번 실행 시각까지다. 기록이 없으면 직전 영업일 07:30부터다.
- 주말·한국 공휴일에는 실행하지 않는다. 공휴일 판단은 `holidays` 패키지(대체공휴일·노동절·선거일 포함)로 하고, 임시공휴일은 `state/extra_holidays.txt`에 날짜를 적는다.
- 실패한 날·연휴가 있어도 다음 성공 실행이 그 기간을 자동으로 합친다. 최대 10일까지 거슬러 올라간다.
- 휴일에 수동으로(`force`) 실행하면 리포트는 만들지만 last_success는 갱신하지 않는다.

## 키워드·분류 (`monitor/config.py`)
- 구조는 섹션 > 소주제 > 키워드다. 분류는 키워드로만 하고, AI는 소주제를 바꾸지 않는다.
- 섹션 순서(WISET → 정부정책 → 유관기관 → 여성과기인 → 참고보도 → 기고칼럼)가 중복 기사 배정 우선순위다.
- 키워드 표기법은 두 가지다.
  - `"여성 최초"`: 붙은 말. 띄어쓰기·가운뎃점은 무시한다.
  - `"교육부+과학"`: 두 단어가 모두 제목·설명에 있으면 된다.
- 네이버는 본문에만 있어도 검색되므로, 제목·설명문에 키워드가 실제로 있는 기사만 남긴다.
- WISET 섹션을 뺀 나머지는 `naver.SOURCES`의 주요 언론사 기사만 후보로 둔다. `SOURCES_DISPLAY_ONLY`는 이름 표시만 하고 후보 범위에는 넣지 않는다.
- 이사장 이름은 윤혜온(현)과 문애리(전) 둘 다 WISET 키워드에 둔다. WISET·이사장·WeSET이 언급된 기사는 코드가 강제로 포함한다.

## AI 선별 (`monitor/select_ai.py`)
- 모델은 `claude-haiku-5-5`(가장 저렴: 입력 $0.10, 출력 $0.50 / 1M 토큰)다. 공식 `anthropic` SDK를 쓰고, 출력은 JSON schema 구조화 출력으로 받는다.
- 호출은 섹션당 1회다. 후보가 400건을 넘는 섹션만 나눠 보내고, 나눠 고른 결과를 한 번 더 합쳐 같은 사안을 묶는다.
- 선별 기준과 예시는 `criteria/examples.json`에 있다(배포본 PDF 분석 결과: `criteria/criteria.md`). 사용자가 "이런 건 빼/넣어"라고 하면 여기에 예시를 추가한다.
- AI가 고른 id는 `title_start`로 제목과 대조한다. 맞지 않으면 제목으로 고치거나 뺀다.
- 섹션당 최대 10건이고, 배포본처럼 보통 1~4건이다. 중요도는 ★★★ 즉시 대응 / ★★☆ 업무 참고 / ★☆☆ 동향 파악.
- 요약은 1~2문장(80자 내외)이고, 사실만 담은 보도체로 쓴다. 근거는 제목과 설명문뿐이다(본문 크롤링 안 함).
- 크레딧 부족·키 오류는 재시도 없이 멈추고, 각 섹션에 키워드 결과 최신 5건과 쉬운 안내를 표시한다.
- 비용 실측: 하루치 1회 $0.025~0.03, 월요일(주말 포함) $0.04, 한 달 약 $0.6(목표 $1 이하).

## 화면 (`monitor/render.py`, `templates/`)
- 모바일 우선 반응형이다. 표(table) 레이아웃은 쓰지 않고, 본문은 16px다. 375px에서 가로 스크롤이 생기면 안 된다.
- 기사 표시 순서: (언론사) 제목(원문 링크, 새 탭) → 요약 → 중요도 → 작성자(칼럼) → 소주제.
- 섹션 탭은 상단에 고정한다. 섹션은 `<details open>`으로 접고 펼치며, WISET 섹션은 맨 위에 보라색으로 표시한다.
- 출력 위치
  - 최신: `docs/index.html`
  - 보관: `docs/archive/YYYY-MM-DD.html`, 목록은 `docs/archive/index.html`
  - 원자료: `docs/data/YYYY-MM-DD.json`
- 아이콘은 `tools/make_icons.py`로 만들고, `docs/manifest.webmanifest`로 홈 화면에 추가할 수 있게 한다.

## 검증 절차
1. `python -m pytest -q`: 수집 기간(화·월·연휴·실패·휴일·중복), 페이지 넘기기, 키워드 규칙, AI 결과 처리, 화면을 검사한다.
2. 키 없이 화면만 볼 때: 저장된 `report.json`으로 `monitor.render.write_report(report, docs=Path("out/preview"))`를 실행한다.
3. `python tools/screenshot.py out/preview/index.html out/shots`: 375px·1280px 캡처와 가로 스크롤·15px 미만 글자를 자동 검사한다(Edge 사용).
4. 실제 키로 시험할 때는 Actions → monitor → Run workflow(`force`)로 돌린다.
   - 로컬에서 쓰는 옵션: `--now`, `--start`, `--dry-run`, `--collect-only`, `--from-candidates`.

## 운영 메모
- Claude 크레딧은 console.anthropic.com → Settings → Billing에서 확인한다.
- push 권한 오류가 나면 저장소 Settings → Actions → General → Workflow permissions를 "Read and write"로 바꾼다.
- 예전 `news_monitor_final(1).py`의 커밋 이력에는 실제 키가 없었다(2026-11-21 확인). 파일은 삭제했다.
