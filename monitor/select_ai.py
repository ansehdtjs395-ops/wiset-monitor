# -*- coding: utf-8 -*-
"""Claude API로 섹션별 기사 선별·요약.

- 모델: Claude Haiku 5.5 (현재 가장 저렴: 입력 $0.10 / 출력 $0.50 per 1M tokens, 10만 토큰 이하 프롬프트 기준)
- 섹션당 1회 호출. 후보가 CHUNK 건을 넘는 섹션만 나눠서 호출(10만 토큰 초과 요금 구간 회피).
- 공통 지시문·예시는 system에 고정 → 프롬프트 캐싱.
"""
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

import anthropic

from .config import COLUMN_SECTION, FORCE_INCLUDE, MAX_PER_SECTION, SECTIONS

MODEL = "claude-haiku-5-5"
PRICE = {"input": 0.10, "output": 0.50, "cache_read": 0.01, "cache_write": 0.125}  # USD / 1M tokens
CHUNK = 400
DESC_CHARS = 100
ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = json.loads((ROOT / "criteria" / "examples.json").read_text(encoding="utf-8"))
IMPORTANCE_ORDER = {"★★★": 0, "★★☆": 1, "★☆☆": 2}

SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "title_start": {"type": "string"},
                    "summary": {"type": "string"},
                    "importance": {"type": "string", "enum": ["★★★", "★★☆", "★☆☆"]},
                    "author": {"type": "string"},
                    "related_ids": {"type": "array", "items": {"type": "integer"}},
                },
                "required": ["id", "title_start", "summary", "importance", "author", "related_ids"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}


def build_system():
    ex = EXAMPLES
    sec_lines = []
    for name, v in ex["sections"].items():
        sec_lines.append(f"### {name}\n기준: {v['criteria']}\n실제로 고른 기사 예시:\n" +
                         "\n".join(f"- {t}" for t in v["examples"]))
    return f"""당신은 한국여성과학기술인육성재단(WISET, 과학기술정보통신부 산하 공공기관) 대외협력홍보팀의 언론모니터링 담당자입니다.
재단 미션: 여성 과학기술인 육성·지원, 이공계 여성 인재 양성, 경력단절 여성 과학기술인 복귀 지원.
이사장: 윤혜온 (전 이사장 문애리). 주요 사업: {", ".join(ex["wiset_programs"])}.
리포트 사용자: 대외협력홍보팀 — 기관장·경영진 보고, 언론 대응, 보도자료 기획.

## 할 일
한 섹션의 후보 기사 목록을 받으면, 판단 질문 "WISET 홍보 담당자가 오늘 경영진에게 보고하거나 업무에 참고할 기사인가?"에 '예'인 기사만 골라 JSON으로 답합니다.

포함: 과기정통부·성평등가족부 등 정부의 과학기술·여성·인재 정책, 출연연·과기원·과총 등 유관기관 활동, 여성 과학기술인·이공계 여성 관련, 과학기술 인재 양성, 일·가정 양립, 공공기관 제도 변화, 과학기술 칼럼·기고·사설(태그가 없어도 내용이 과학기술이면 포함).
제외: 범죄·사건사고(단, 출연연·과기원·과기부의 비리·감사는 포함), 연예·스포츠·패션, 과학기술과 무관한 의료·성형, 부동산·주식, 지역 단신·홍보성 행사 기사, 키워드가 들어가도 맥락이 무관한 기사.
제외 예시: {" / ".join(ex["exclude_examples"])}
[필수] 표시가 붙은 기사(WISET·이사장 직접 언급)는 반드시 포함합니다.

## 선별 원칙
- 실제 배포본처럼 엄격하게: 섹션당 보통 1~4건, 많아도 {MAX_PER_SECTION}건. 해당 기사가 없으면 빈 목록도 정상입니다.
- 기관명이 기사에 '언급만' 된 것으로는 부족합니다. 그 기관의 정책·발표·인사·예산·행사가 기사의 중심이어야 합니다.
  예) 정부정책동향: 과기정통부의 과학기술·AI·인재 정책, R&D 예산, 장·차관 발언·동정, 여성·성평등·일가정양립 정책과 통계가 중심.
      사회 사건 보도(수능 부정행위 사건 경과 등)는 과학기술 정책 대응이 핵심인 대표 기사 1건만, 지역 인프라 공모·홍보성 행사는 제외.
- 같은 사안(같은 사건·발표·행사)은 반드시 1건으로 묶습니다. 대표 1건만 고르고(주요 일간지·통신사 우선, 내용이 가장 충실한 것), 나머지 id는 related_ids에 넣습니다.
- 중요도: ★★★ WISET 직접 관련·즉시 대응 필요 / ★★☆ 업무 참고(재단 업무·여성과학기술인·과기 인재 정책에 직접 영향) / ★☆☆ 동향 파악(그 밖의 참고 기사, 대부분은 여기). 중요도 높은 순으로 나열합니다.
- author: 기고·칼럼·사설이면 작성자 "이름 소속 직함"(예: "오상록 KIST 원장"), 사설은 "사설", 알 수 없거나 일반 기사면 "".

- title_start: 고른 기사(id) 제목의 앞 10글자를 그대로 적습니다. id와 제목이 맞는지 확인하는 용도입니다.

## 요약 작성 원칙
- 1~2문장, 80자 내외. 기사에 나온 사실만, 추측·평가 금지.
- 누가, 무엇을, 왜 중요한지 중심. 숫자·정책명·기관명이 있으면 포함.
- 제목을 그대로 반복하지 않기. "~했다", "~밝혔다" 같은 보도체.
- 주어진 제목과 설명문만 근거로 씁니다.

## 섹션별 기준과 실제 선별 예시 (담당자가 과거에 직접 고른 기사)
{chr(10).join(sec_lines)}

## 입력 형식
한 줄에 기사 하나: id | 언론사 | 소주제 | 제목 | 설명문 앞부분
"""


SYSTEM = build_system()


def is_forced(a):
    text = a["title"] + " " + a["desc"]
    return any(k.lower() in text.lower() for k in FORCE_INCLUDE)


def clip(t, n=90):
    t = (t or "").strip()
    return t if len(t) <= n else t[:n].rstrip() + "…"


def _sq(t):
    return re.sub(r"[\W_]+", "", t or "").lower()


def resolve_id(it, titles, offset=0):
    """AI가 준 id가 title_start와 맞는지 확인. 틀리면 제목으로 찾아 고치고, 못 찾으면 None."""
    head = _sq(re.sub(r"^\s*\[필수\]\s*", "", it.get("title_start", "")))[:8]
    idx = it["id"] - offset

    def close(t):
        body = _sq(re.sub(r"^(\s*[\[(【<][^\])】>]*[\])】>])+", "", t))  # 앞쪽 [말머리] 제거
        full = _sq(t)
        return (head in full[:40] or head in body[:40]
                or SequenceMatcher(None, head, body[:len(head)]).ratio() >= 0.75
                or SequenceMatcher(None, head, full[:len(head)]).ratio() >= 0.75)

    if not head:
        return idx if 0 <= idx < len(titles) else None
    if 0 <= idx < len(titles) and close(titles[idx]):
        return idx
    matches = [i for i, t in enumerate(titles) if close(t)]
    return matches[0] if len(matches) == 1 else None


def _fmt(i, a):
    desc = a["desc"][:DESC_CHARS].replace("\n", " ")
    flag = "[필수] " if is_forced(a) else ""
    return f"{i} | {a['source']} | {a['sub']} | {flag}{a['title']} | {desc}"


class Selector:
    def __init__(self, api_key, log=print):
        self.client = anthropic.Anthropic(api_key=api_key, max_retries=3, timeout=180)
        self.log = log
        self.usage = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "calls": 0}
        self.fatal = None  # 크레딧 부족·키 오류처럼 재시도해도 소용없는 오류

    def cost(self):
        return sum(self.usage[k] * PRICE[k] for k in PRICE) / 1_000_000

    def _call(self, section, lines, user=None):
        crit = EXAMPLES["sections"].get(section, {}).get("criteria", "")
        extra = "칼럼·기고·사설은 author를 꼭 채우세요." if section == COLUMN_SECTION else ""
        if user is None:
            user = f"섹션: {section}\n이 섹션 기준: {crit}\n{extra}\n\n후보 기사 {len(lines)}건:\n" + "\n".join(lines)
        else:
            user = f"이 섹션 기준: {crit}\n" + user
        resp = self.client.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        )
        u = resp.usage
        self.usage["calls"] += 1
        self.usage["input"] += u.input_tokens
        self.usage["output"] += u.output_tokens
        self.usage["cache_read"] += u.cache_read_input_tokens or 0
        self.usage["cache_write"] += u.cache_creation_input_tokens or 0
        if resp.stop_reason == "refusal":
            raise RuntimeError("모델이 응답을 거절함")
        if resp.stop_reason == "max_tokens":
            raise RuntimeError("출력 길이 초과")
        text = next(b.text for b in resp.content if b.type == "text")
        return json.loads(text)["items"]

    def _merge(self, section, picked):
        """여러 묶음으로 나눠 고른 결과를 한 번 더 모아 같은 사안 합치기 + 상위 선별 (후보가 많은 날만)."""
        lines = [f"{i} | {a['source']} | {a['importance']} | {a['title']} | {a['summary']}" for i, a in enumerate(picked)]
        user = (f"섹션: {section}\n아래는 이 섹션 후보를 여러 묶음으로 나눠 이미 고른 기사입니다. 같은 사안끼리 묶어 대표 1건만 남기고"
                f"(나머지는 related_ids), 섹션 기준에 맞는 기사만 중요도순으로 최대 {MAX_PER_SECTION}건 고르세요. "
                f"summary·author는 주어진 것을 그대로 쓰세요. 입력 형식: id | 언론사 | 중요도 | 제목 | 요약\n\n"
                + "\n".join(lines))
        items = self._call(section, None, user=user)
        out = []
        titles = [a["title"] for a in picked]
        for it in items:
            i = resolve_id(it, titles)
            if i is None:
                continue
            a = picked[i]
            rel = list(a["related"])
            for r in it["related_ids"]:
                if 0 <= r < len(picked) and r != i:
                    b = picked[r]
                    rel.append({"title": b["title"], "source": b["source"], "link": b["link"]})
                    rel.extend(b["related"])
            out.append({**a, "importance": it["importance"], "related": rel})
        return out

    def select_section(self, section, subs):
        arts = [a for sub in SECTIONS[section] for a in subs.get(sub, [])]
        if not arts:
            return [], None
        picked = []
        error = None
        for c0 in range(0, len(arts), CHUNK):
            chunk = arts[c0:c0 + CHUNK]
            lines = [_fmt(c0 + i, a) for i, a in enumerate(chunk)]
            items = None
            for attempt in range(2):
                if self.fatal:
                    error = self.fatal
                    break
                try:
                    items = self._call(section, lines)
                    break
                except anthropic.AuthenticationError:
                    self.fatal = error = "Claude API 키 오류 — GitHub Secrets의 CLAUDE_API_KEY 확인 필요"
                except anthropic.PermissionDeniedError:
                    self.fatal = error = "Claude API 권한 오류 — 키의 사용 권한 확인 필요"
                except anthropic.BadRequestError as e:
                    if "credit balance" in str(e):
                        self.fatal = error = "Claude API 크레딧 부족 — console.anthropic.com에서 충전 필요"
                    else:
                        error = f"요청 오류: {getattr(e, 'message', e)}"
                    self.log(f"  ! {section} AI 호출 실패: {error}")
                    if self.fatal:
                        break
                except (anthropic.APIError, RuntimeError, json.JSONDecodeError, StopIteration, KeyError) as e:
                    error = f"{type(e).__name__}: {e}"
                    self.log(f"  ! {section} AI 호출 실패({attempt + 1}회): {error}")
            if items is None:
                continue
            titles = [a["title"] for a in chunk]
            for it in items:
                local = resolve_id(it, titles, offset=c0)
                if local is None:
                    self.log(f"  ! {section}: id {it['id']}와 제목 '{it.get('title_start', '')}'이 맞지 않아 제외")
                    continue
                idx = c0 + local
                rel = sorted({r for r in it["related_ids"] if c0 <= r < c0 + len(chunk) and r != idx})
                summary = it["summary"].strip() or clip(arts[idx]["desc"])
                picked.append({**arts[idx], "summary": summary, "importance": it["importance"],
                               "author": it["author"].strip(),
                               "related": [{"title": arts[r]["title"], "source": arts[r]["source"],
                                            "link": arts[r]["link"]} for r in rel]})

        if not picked and error:
            # AI 실패: 키워드 결과 상위 기사로 대체 (요약 대신 설명문)
            fallback = sorted(arts, key=lambda a: a["pub"], reverse=True)[:5]
            return [{**a, "summary": clip(a["desc"]), "importance": "★☆☆", "author": "", "related": []}
                    for a in fallback], f"AI 선별 실패: 키워드 검색 결과 최신 기사 5건을 대신 표시 ({error[:80]})"

        if len(arts) > CHUNK and len(picked) > 1:
            try:
                picked = self._merge(section, picked)
            except (anthropic.APIError, RuntimeError, json.JSONDecodeError, StopIteration, KeyError) as e:
                self.log(f"  ! {section} 묶음 합치기 실패, 묶음별 결과 사용: {e}")

        # 필수 기사 누락 방지
        have = {a["link"] for a in picked} | {r["link"] for a in picked for r in a["related"]}
        for a in arts:
            if is_forced(a) and a["link"] not in have:
                picked.append({**a, "summary": clip(a["desc"]), "importance": "★★★", "author": "", "related": []})
                have.add(a["link"])

        # 청크 간 중복 사안: 같은 링크 제거 후 중요도순 정렬, 상한 적용 (필수 기사는 상한과 무관)
        seen, uniq = set(), []
        for a in picked:
            if a["link"] not in seen:
                seen.add(a["link"])
                uniq.append(a)
        uniq.sort(key=lambda a: a["pub"], reverse=True)
        uniq.sort(key=lambda a: IMPORTANCE_ORDER.get(a["importance"], 3))
        forced = [a for a in uniq if is_forced(a)]
        rest = [a for a in uniq if not is_forced(a)][:max(0, MAX_PER_SECTION - len(forced))]
        out = sorted(forced + rest, key=lambda a: IMPORTANCE_ORDER.get(a["importance"], 3))
        return out, None

    def select_all(self, candidates):
        result = {}
        for section in SECTIONS:
            subs = candidates.get(section, {})
            n = sum(len(v) for v in subs.values())
            items, note = self.select_section(section, subs)
            self.log(f"  {section}: 후보 {n}건 → 선별 {len(items)}건" + (f" ({note})" if note else ""))
            result[section] = {"items": items, "note": note, "candidates": n}
        return result
