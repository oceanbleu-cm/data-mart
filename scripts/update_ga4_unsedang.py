#!/usr/bin/env python3
"""
운세당 GA4 퍼널 리포트(html/ga4-funnel-unsedang.html) 롤링-윈도우 업데이트 스크립트.

이 리포트는 2026-09-30에 구조가 완전히 바뀌었다 — 예전에는 연초부터 날짜를 영구
누적하는 방식이었지만, 지금은 `html/ga4-channel-unsedang.html`과 같은 철학의
**롤링(sliding) 윈도우(최근 90일)**다. 그래서 매 실행마다:
  1) 새로 확정된 날짜(들)를 DAILY_PAGES/DAILY_CALL에 추가하고
  2) 윈도우 밖으로 밀려난 오래된 날짜를 제거하고(윈도우 항상 90일 유지)
  3) 기간 합계(PAGE_TOTALS, CALL_TOTAL)는 "새 날짜만 반영"이 아니라 **매번 새 윈도우
     전체를 재조회한 값으로 통째로 교체**한다 — activeUsers는 비집계 지표라 날짜를
     밀어내고 더하는 방식으로는 정확한 값을 유지할 수 없기 때문이다.

이 스크립트는 Supermetrics를 직접 호출하지 않는다(에이전트만 MCP 툴 호출 가능).
`.claude/commands/update-ga4-unsedang.md`가 미리 8개의 임시 JSON 파일을 만들어두면
이 스크립트가 그것을 읽어 HTML에 반영한다.

퍼널 단계(STEPS, 화면 표시 순서)는 홈메인 → 상담사 목록 → 상담사 상세 → AI 상담목록 →
AI 상담보기 → 상담하기 → 운세 → 후기다. 앞의 6단계(상담하기 제외)는 페이지(PAGE_KEYS),
"상담하기"는 pre_tel_click(선불)과 post_tel_click(후불) 두 이벤트를 하나의 필터로 묶어
activeUsers를 재조회한 값(DAILY_CALL/CALL_TOTAL, 페이지와 무관한 별도 시리즈)이다.

이 외에 화면에는 세 가지 지표가 더 있다 — 전부 이 스크립트가 함께 롤링한다:
  - DAILY_SITE/SITE_ACTIVE_USERS_TOTAL: "전체사용자"(최상단에 표시). 페이지/이벤트
    dimension 없이 사이트 전체를 집계한 별도 시리즈.
  - DAILY_SUBEVENTS/SUBEVENT_TOTALS: "상담사 상세"/"AI 상담보기" 아래 하위그룹 7개 이벤트
    (EVENT_KEYS, 전부 eventName 그대로가 키 — 예: ai-note-agree-pop). 2026-09-30부터
    신규 집계된 이벤트라 그 이전 날짜는 0이 정상이다.
  - DAILY_FIRST_USER/FIRST_USER_TOTALS: "전체사용자" 아래 "매체별 유입" 하위그룹
    (GROUP_KEYS 7개 — lg/notSet/direct/naverGrp/googleGrp/kakaoGrp/etcGrp). GA4
    firstUserSource 원본 값을 FIRST_USER_LABEL_TO_GROUP(+ 모르는 값은 classify_source()
    자동 분류)으로 그룹핑한 것으로, `html/ga4-channel-unsedang.html`
    (`update_ga4_channel_unsedang.py`)의 매체별 유입 그룹과 같은 분류 기준이지만
    이 리포트의 90일 전체 창을 대상으로 별도 롤링된다. firstUserSource는 사용자당
    평생 하나뿐인 값이라 단순 합산이 정확하다 — 병합 쿼리 불필요.

사용법:
    python3 update_ga4_unsedang.py --html <path> --indir <tmpdir> [--dry-run]
                                    [--generated-at STR] [--no-backup]

입력 디렉터리(--indir) 안의 8개 파일 스키마:
    pages_incremental.json : {"rows": [{"date","path","activeUsers","sessions"}, ...]}
                              (증분 구간: 마지막 수록일 다음날 ~ 새 to. path는 PAGE_PATH_TO_KEY의
                               7개 값 중 하나여야 한다 — 오타/신규 경로는 SafetyError.)
    pages_period.json      : {"rows": [{"path","activeUsers"}, ...]}
                              (새 윈도우 전체, dimension에서 date를 뺀 경로별 재조회 — 비집계
                               지표 순사용자 수. 값이 0인 경로는 행을 만들지 않아도 된다.)
    call_incremental.json  : {"rows": [{"date","activeUsers","eventCount"}, ...]}
                              (eventName IN (pre_tel_click, post_tel_click) 필터, dimension은
                               date만 — eventName을 dimension에 넣지 말 것(중복 집계 방지).)
    call_period.json       : {"rows": [{"activeUsers","eventCount"}]}  (한 행, 새 윈도우 전체,
                              dimension 없이 같은 필터로 재조회.)
    site_incremental.json  : {"rows": [{"date","activeUsers"}, ...]}
                              (증분 구간, dimension 없이 사이트 전체 activeUsers — date만 넣는다.)
    site_period.json       : {"rows": [{"activeUsers"}]}  (한 행, 새 윈도우 전체, dimension 없음.)
    subevents_incremental.json : {"rows": [{"date","eventName","activeUsers"}, ...]}
                              (eventName IN EVENT_KEYS(7개) 필터, dimension은 date+eventName.
                               eventName이 EVENT_KEYS에 없으면 SafetyError.)
    subevents_period.json  : {"rows": [{"eventName","activeUsers"}, ...]}
                              (새 윈도우 전체, dimension은 eventName만(date 뺌). 가장 최근 런칭된
                               이벤트라 거의 모든 값이 0 — 값이 0인 eventName은 행을 만들지
                               않아도 된다.)
    firstuser_raw_incremental.json : {"rows": [{"date","source","activeUsers","sessions"}, ...]}
                              (증분 구간, dimension은 date+firstUserSource, 필터 없음. source는
                               GA4 원본 firstUserSource 값 그대로 — 그룹별 일별 값은 이 원본
                               행들을 FIRST_USER_LABEL_TO_GROUP(+classify_source())으로 단순
                               합산해서 만든다. 알려진 매핑 테이블에 없는 새 값이 나와도
                               SafetyError로 중단하지 않고 classify_source()가 자동 분류한다
                               (경고만 남김).)
    firstuser_raw_period.json : {"rows": [{"source","activeUsers"}, ...]}
                              (새 윈도우 전체, dimension은 firstUserSource만(date 뺌) — 그룹별
                               기간 합계도 마찬가지로 단순 합산해서 만든다.)
"""
import argparse
import json
import os
import re
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone

WINDOW_DAYS = 90

PAGE_PATH_TO_KEY = {
    '/view/home': 'home',
    '/view/csl': 'csl',
    '/view/ai-note': 'aiNote',
    '/view/ai-note/noteInfo': 'aiNoteInfo',
    '/view/csl/cslInfo': 'cslInfo',
    '/view/content': 'content',
    '/view/csl/totalRatingComment': 'totalRatingComment',
}
PAGE_KEYS = ['home', 'csl', 'aiNote', 'aiNoteInfo', 'cslInfo', 'content', 'totalRatingComment']

EVENT_KEYS = [
    'ai-note-agree-pop',
    'ai-note-cancel-click',
    'ai-note-agree-click',
    'ai-note-review-skip',
    'ai-note-review-next',
    'ai-note-review-submit',
    'ai-note-councel-click',
]

# --- "전체사용자" 아래 "매체별 유입" 하위그룹 — ga4-channel-unsedang.html
# (update_ga4_channel_unsedang.py)과 동일한 분류 기준. ''(빈 문자열)은 GA4가 소스를
# 확인하지 못해 내려준 값 — '(not set)'과 동일하게 취급.
GROUP_KEYS = ['lg', 'notSet', 'direct', 'naverGrp', 'googleGrp', 'kakaoGrp', 'etcGrp']

FIRST_USER_LABEL_TO_GROUP = {
    'LG': 'lg',
    '(not set)': 'notSet',
    '(direct)': 'direct',
    '': 'notSet',
    'm.search.naver.com': 'naverGrp',
    'naver': 'naverGrp',
    'navercafe': 'naverGrp',
    'm.ad.search.naver.com': 'naverGrp',
    'google': 'googleGrp',
    'google-play': 'googleGrp',
    'kakao': 'kakaoGrp',
    'kakao_alimtalk': 'kakaoGrp',
    'unsedang_portal': 'etcGrp',
    'banner_01': 'etcGrp',
}


def classify_source(raw):
    """알려진 매핑 테이블에 없는 새 firstUserSource 원본 값을 자동 분류한다.
    'naver'가 포함되면(대소문자 무시) naverGrp, 'google'이 포함되면 googleGrp,
    'kakao'가 포함되면 kakaoGrp, '(not set)'/''(빈 문자열)이면 notSet, 그 외 전부 etcGrp."""
    if raw in ('(not set)', ''):
        return 'notSet'
    low = raw.lower()
    if 'naver' in low:
        return 'naverGrp'
    if 'google' in low:
        return 'googleGrp'
    if 'kakao' in low:
        return 'kakaoGrp'
    return 'etcGrp'


def group_of(raw):
    return FIRST_USER_LABEL_TO_GROUP.get(raw) or classify_source(raw)


GENERATED_AT_FMT = '%Y-%m-%d %H:%M UTC (Supermetrics GA4/GAWA 조회, 정적 스냅샷)'


class SafetyError(Exception):
    """검증 실패 — 원본 파일은 절대 건드리지 않고 여기서 중단."""


# ---------------------------------------------------------------------------
# 1. 기존 HTML 파싱 — DAILY_PAGES/DAILY_CALL/PAGE_TOTALS/CALL_TOTAL/DATE_RANGE 전부
#    `  const NAME = {...};` 형태의 단일 줄 블록이다.
# ---------------------------------------------------------------------------

def extract_single_line_block(src, name, indent='  '):
    pattern = re.compile(r'^' + re.escape(indent) + r'const ' + re.escape(name) + r' = (\{.*?\});$', re.M)
    m = pattern.search(src)
    if not m:
        raise SafetyError(f'{name} 블록을 찾지 못했습니다 — HTML 구조가 바뀐 것 같습니다. 수동 확인 필요.')
    return m.start(), m.end(), m.group(1)


def parse_daily_pages(body):
    """`{"home":{...},"csl":{...},...}` — 페이지 7개 키의 {date:[u,s]} 딕셔너리."""
    data = json.loads(body)
    for key in PAGE_KEYS:
        data.setdefault(key, {})
    return data


def parse_daily_call(body):
    """`{"2026-07-02":[u,c], ...}` — 날짜 플랫 딕셔너리(페이지처럼 key로 한 번 더 감싸지 않음)."""
    return json.loads(body)


def parse_daily_site(body):
    """`{"2026-07-02":358, ...}` — 날짜 플랫 딕셔너리, 값은 스칼라(activeUsers) 하나뿐."""
    return json.loads(body)


def parse_daily_subevents(body):
    """`{"ai-note-agree-pop":{date:u, ...}, ...}` — EVENT_KEYS 7개 키의 {date:activeUsers} 딕셔너리."""
    data = json.loads(body)
    for key in EVENT_KEYS:
        data.setdefault(key, {})
    return data


def parse_subevent_totals(body):
    """`{"ai-note-agree-pop":0, ...}` — EVENT_KEYS 기간 합계(activeUsers), 키에 하이픈이 있어 JSON 그대로 파싱."""
    data = json.loads(body)
    for key in EVENT_KEYS:
        data.setdefault(key, 0)
    return data


def parse_daily_first_user(body):
    """`{"lg":{...},"notSet":{...},...}` — GROUP_KEYS 7개 키의 {date:[u,s]} 딕셔너리."""
    data = json.loads(body)
    for key in GROUP_KEYS:
        data.setdefault(key, {})
    return data


def parse_js_number_object(body):
    """`{ home: 11130, csl: 1998, ... }` 같은 JS 리터럴(키 따옴표 없음)을 파싱."""
    out = {}
    for m in re.finditer(r'(\w+):\s*(-?\d+)', body):
        out[m.group(1)] = int(m.group(2))
    return out


def parse_scalars(src):
    m = re.search(r"const DATE_RANGE = \{ from: '([\d-]+)', to: '([\d-]+)' \};", src)
    if not m:
        raise SafetyError('DATE_RANGE 상수를 찾지 못했습니다.')
    return {'from': m.group(1), 'to': m.group(2)}


def parse_site_total(src):
    m = re.search(r'const SITE_ACTIVE_USERS_TOTAL = (\d+);', src)
    if not m:
        raise SafetyError('SITE_ACTIVE_USERS_TOTAL 상수를 찾지 못했습니다.')
    return int(m.group(1))


# ---------------------------------------------------------------------------
# 2. 신규 데이터 로드
# ---------------------------------------------------------------------------

def _read_rows(indir, fname):
    path = os.path.join(indir, fname)
    if not os.path.exists(path):
        raise SafetyError(f'{indir}에 {fname}이 없습니다.')
    with open(path, encoding='utf-8') as f:
        return json.load(f).get('rows', [])


def load_pages_incremental(indir):
    """반환: ({key: {date: [u,s]}}, all_dates)."""
    incr = {k: {} for k in PAGE_KEYS}
    rows = _read_rows(indir, 'pages_incremental.json')
    for r in rows:
        key = PAGE_PATH_TO_KEY.get(r['path'])
        if key is None:
            raise SafetyError(
                f"알 수 없는 페이지 경로: {r['path']!r} — 오타이거나 STEPS에 없는 신규 경로입니다. "
                f'의도적인 신규 단계 추가라면 PAGE_PATH_TO_KEY/PAGE_KEYS와 HTML의 STEPS/DAILY_PAGES를 '
                f'먼저 함께 갱신하세요(이 스크립트만으로는 새 단계를 추가할 수 없습니다).'
            )
        incr[key][r['date']] = [r['activeUsers'] or 0, r['sessions']]
    all_dates = sorted({d for series in incr.values() for d in series})
    return incr, all_dates


def load_pages_period(indir):
    """반환: {key: activeUsers}. 값이 없는 경로는 0으로 채운다(트래픽 0인 것이 정상 — 예: AI 상담)."""
    totals = {k: 0 for k in PAGE_KEYS}
    rows = _read_rows(indir, 'pages_period.json')
    for r in rows:
        key = PAGE_PATH_TO_KEY.get(r['path'])
        if key is None:
            raise SafetyError(f"pages_period.json: 알 수 없는 페이지 경로 {r['path']!r}")
        totals[key] = r['activeUsers'] or 0
    return totals


def load_call_incremental(indir):
    """반환: ({date: [u,c]}, all_dates)."""
    daily = {}
    rows = _read_rows(indir, 'call_incremental.json')
    for r in rows:
        daily[r['date']] = [r['activeUsers'] or 0, r['eventCount']]
    return daily, sorted(daily)


def load_call_period(indir):
    rows = _read_rows(indir, 'call_period.json')
    if not rows:
        raise SafetyError('call_period.json에 결과 행이 없습니다 — GA4 쿼리가 비정상일 가능성이 있습니다.')
    r = rows[0]
    return {'activeUsers': r['activeUsers'] or 0, 'eventCount': r['eventCount']}


def load_site_incremental(indir):
    """반환: ({date: activeUsers}, all_dates)."""
    daily = {}
    rows = _read_rows(indir, 'site_incremental.json')
    for r in rows:
        daily[r['date']] = r['activeUsers'] or 0
    return daily, sorted(daily)


def load_site_period(indir):
    rows = _read_rows(indir, 'site_period.json')
    if not rows:
        raise SafetyError('site_period.json에 결과 행이 없습니다 — GA4 쿼리가 비정상일 가능성이 있습니다.')
    return rows[0]['activeUsers'] or 0


def load_subevents_incremental(indir):
    """반환: ({eventName: {date: activeUsers}}, all_dates)."""
    incr = {k: {} for k in EVENT_KEYS}
    rows = _read_rows(indir, 'subevents_incremental.json')
    for r in rows:
        if r['eventName'] not in incr:
            raise SafetyError(
                f"알 수 없는 하위그룹 eventName: {r['eventName']!r} — 오타이거나 EVENT_KEYS에 없는 "
                f'신규 이벤트입니다. 의도적인 신규 이벤트 추가라면 EVENT_KEYS와 HTML의 SUBGROUPS를 '
                f'먼저 함께 갱신하세요(이 스크립트만으로는 새 하위그룹 이벤트를 추가할 수 없습니다).'
            )
        incr[r['eventName']][r['date']] = r['activeUsers'] or 0
    all_dates = sorted({d for series in incr.values() for d in series})
    return incr, all_dates


def load_subevents_period(indir):
    """반환: {eventName: activeUsers}. 값이 없는 이벤트는 0으로 채운다(신규 런칭 직후라 0이 정상)."""
    totals = {k: 0 for k in EVENT_KEYS}
    rows = _read_rows(indir, 'subevents_period.json')
    for r in rows:
        if r['eventName'] not in totals:
            raise SafetyError(f"subevents_period.json: 알 수 없는 eventName {r['eventName']!r}")
        totals[r['eventName']] = r['activeUsers'] or 0
    return totals


def load_firstuser_incremental(indir):
    """firstuser_raw_incremental.json을 FIRST_USER_LABEL_TO_GROUP으로 단순 합산(정확함 —
    firstUserSource는 사용자당 평생 1개). 매핑에 없는 값은 classify_source()로 자동
    분류해서 그대로 합산에 포함한다(SafetyError로 중단하지 않음 — 경고만 남김).
    반환: ({group: {date: [u,s]}}, all_dates, warnings)."""
    incr = {k: {} for k in GROUP_KEYS}
    rows = _read_rows(indir, 'firstuser_raw_incremental.json')
    unknown = sorted({r['source'] for r in rows if r['source'] not in FIRST_USER_LABEL_TO_GROUP})
    warnings = [
        f"신규 firstUserSource 값 '{lbl}' → {classify_source(lbl)} 자동 분류(사람 확인 권장)"
        for lbl in unknown
    ]
    for r in rows:
        g = group_of(r['source'])
        bucket = incr[g].setdefault(r['date'], [0, 0])
        bucket[0] += r['activeUsers'] or 0
        bucket[1] += r['sessions'] or 0
    all_dates = sorted({d for series in incr.values() for d in series})
    return incr, all_dates, warnings


def load_firstuser_period(indir):
    """firstuser_raw_period.json을 그룹별로 단순 합산해 기간 합계(activeUsers)를 만든다.
    반환: ({group: activeUsers}, warnings)."""
    totals = {k: 0 for k in GROUP_KEYS}
    rows = _read_rows(indir, 'firstuser_raw_period.json')
    unknown = sorted({r['source'] for r in rows if r['source'] not in FIRST_USER_LABEL_TO_GROUP})
    warnings = [
        f"신규 firstUserSource 값(기간 합계) '{lbl}' → {classify_source(lbl)} 자동 분류(사람 확인 권장)"
        for lbl in unknown
    ]
    for r in rows:
        totals[group_of(r['source'])] += r['activeUsers'] or 0
    return totals, warnings


# ---------------------------------------------------------------------------
# 3. 병합 + 윈도우 슬라이딩
# ---------------------------------------------------------------------------

def merge_and_slide(old_series, incr_series, new_from, new_to):
    """old_series: {date: [...]}. incr_series 값으로 덮어쓰기 허용(최근 며칠은 GA4 처리 지연으로
    재확정되며 값이 바뀔 수 있다). 그 다음 [new_from, new_to] 밖 날짜는 전부 제거해 윈도우를
    정확히 WINDOW_DAYS일로 유지한다."""
    combined = dict(old_series)
    combined.update(incr_series)
    return dict(sorted((d, v) for d, v in combined.items() if new_from <= d <= new_to))


def window_dates(new_from, new_to):
    d0 = date.fromisoformat(new_from)
    d1 = date.fromisoformat(new_to)
    return [(d0 + timedelta(days=i)).isoformat() for i in range((d1 - d0).days + 1)]


# ---------------------------------------------------------------------------
# 4. 검증
# ---------------------------------------------------------------------------

def validate(new_daily_pages, new_page_totals, new_daily_call, new_call_total,
             new_daily_site, new_site_total, new_daily_subevents, new_subevent_totals,
             new_daily_first_user, new_first_user_totals,
             new_from, new_to):
    warnings = []

    for key, series in new_daily_pages.items():
        for d, (u, s) in series.items():
            if d < new_from or d > new_to:
                raise SafetyError(f'G-WINDOW 위반: DAILY_PAGES.{key} {d}가 윈도우({new_from}~{new_to}) 밖에 남아있습니다.')
            if u < 0 or s < 0:
                raise SafetyError(f'G6 위반: DAILY_PAGES.{key} {d} 값에 음수 포함 ({u}, {s})')

    for d, (u, c) in new_daily_call.items():
        if d < new_from or d > new_to:
            raise SafetyError(f'G-WINDOW 위반: DAILY_CALL {d}가 윈도우 밖에 남아있습니다.')
        if u < 0 or c < 0:
            raise SafetyError(f'G6 위반: DAILY_CALL {d} 값에 음수 포함 ({u}, {c})')

    for key in PAGE_KEYS:
        day_vals = [v[0] for v in new_daily_pages[key].values()]
        period_val = new_page_totals[key]
        if period_val < 0:
            raise SafetyError(f'G6 위반: PAGE_TOTALS.{key}가 음수입니다.')
        if day_vals:
            day_sum, day_max = sum(day_vals), max(day_vals)
            if not (day_max <= period_val <= day_sum):
                warnings.append(
                    f'PAGE_TOTALS.{key}: 기간 합계(dedup)={period_val}가 일별 활성사용자 범위 '
                    f'[{day_max}, {day_sum}] 밖입니다 — 재조회 결과를 확인하세요(경고만, 중단하지 않음).'
                )

    call_day_vals = [v[0] for v in new_daily_call.values()]
    if new_call_total['activeUsers'] < 0 or new_call_total['eventCount'] < 0:
        raise SafetyError('G6 위반: CALL_TOTAL에 음수가 있습니다.')
    if call_day_vals:
        day_sum, day_max = sum(call_day_vals), max(call_day_vals)
        if not (day_max <= new_call_total['activeUsers'] <= day_sum):
            warnings.append(
                f"CALL_TOTAL.activeUsers={new_call_total['activeUsers']}가 일별 활성사용자 범위 "
                f'[{day_max}, {day_sum}] 밖입니다 — 확인 권장(경고만, 중단하지 않음).'
            )
        event_day_sum = sum(v[1] for v in new_daily_call.values())
        if event_day_sum != new_call_total['eventCount']:
            warnings.append(
                f"CALL_TOTAL.eventCount={new_call_total['eventCount']}가 일별 합계({event_day_sum})와 "
                f'다릅니다 — eventCount는 집계 가능 지표라 원래 일치해야 합니다(경고만, 중단하지 않음).'
            )

    expected_dates = set(window_dates(new_from, new_to))
    missing_call_dates = expected_dates - set(new_daily_call)
    if missing_call_dates:
        warnings.append(f'DAILY_CALL에 누락된 날짜: {sorted(missing_call_dates)[:5]}... (GA4가 0으로 응답했거나 쿼리 범위 확인 필요)')

    for d, u in new_daily_site.items():
        if d < new_from or d > new_to:
            raise SafetyError(f'G-WINDOW 위반: DAILY_SITE {d}가 윈도우 밖에 남아있습니다.')
        if u < 0:
            raise SafetyError(f'G6 위반: DAILY_SITE {d} 값이 음수입니다 ({u})')
    if new_site_total < 0:
        raise SafetyError('G6 위반: SITE_ACTIVE_USERS_TOTAL이 음수입니다.')
    site_day_vals = list(new_daily_site.values())
    if site_day_vals:
        day_sum, day_max = sum(site_day_vals), max(site_day_vals)
        if not (day_max <= new_site_total <= day_sum):
            warnings.append(
                f'SITE_ACTIVE_USERS_TOTAL={new_site_total}가 일별 활성사용자 범위 '
                f'[{day_max}, {day_sum}] 밖입니다 — 확인 권장(경고만, 중단하지 않음).'
            )
    missing_site_dates = expected_dates - set(new_daily_site)
    if missing_site_dates:
        warnings.append(f'DAILY_SITE에 누락된 날짜: {sorted(missing_site_dates)[:5]}... (사이트 전체 지표라 매일 값이 있어야 정상)')

    for key, series in new_daily_subevents.items():
        for d, u in series.items():
            if d < new_from or d > new_to:
                raise SafetyError(f'G-WINDOW 위반: DAILY_SUBEVENTS.{key} {d}가 윈도우 밖에 남아있습니다.')
            if u < 0:
                raise SafetyError(f'G6 위반: DAILY_SUBEVENTS.{key} {d} 값이 음수입니다 ({u})')
        period_val = new_subevent_totals[key]
        if period_val < 0:
            raise SafetyError(f'G6 위반: SUBEVENT_TOTALS.{key}가 음수입니다.')
        day_vals = [v for v in series.values()]
        if day_vals:
            day_sum, day_max = sum(day_vals), max(day_vals)
            if not (day_max <= period_val <= day_sum):
                warnings.append(
                    f'SUBEVENT_TOTALS.{key}: 기간 합계(dedup)={period_val}가 일별 활성사용자 범위 '
                    f'[{day_max}, {day_sum}] 밖입니다 — 재조회 결과를 확인하세요(경고만, 중단하지 않음).'
                )

    for key, series in new_daily_first_user.items():
        for d, (u, s) in series.items():
            if d < new_from or d > new_to:
                raise SafetyError(f'G-WINDOW 위반: DAILY_FIRST_USER.{key} {d}가 윈도우 밖에 남아있습니다.')
            if u < 0 or s < 0:
                raise SafetyError(f'G6 위반: DAILY_FIRST_USER.{key} {d} 값에 음수 포함 ({u}, {s})')
        period_val = new_first_user_totals[key]
        if period_val < 0:
            raise SafetyError(f'G6 위반: FIRST_USER_TOTALS.{key}가 음수입니다.')
        day_vals = [v[0] for v in series.values()]
        if day_vals:
            day_sum, day_max = sum(day_vals), max(day_vals)
            if not (day_max <= period_val <= day_sum):
                warnings.append(
                    f'FIRST_USER_TOTALS.{key}: 기간 합계={period_val}가 일별 활성사용자 범위 '
                    f'[{day_max}, {day_sum}] 밖입니다 — 재조회 결과를 확인하세요(경고만, 중단하지 않음).'
                )

    return warnings


# ---------------------------------------------------------------------------
# 5. 재직렬화 — 전부 한 줄짜리 `  const NAME = {...};` 블록
# ---------------------------------------------------------------------------

def render_daily_pages(data):
    ordered = {k: dict(sorted(data[k].items())) for k in PAGE_KEYS}
    json_str = json.dumps(ordered, separators=(',', ':'))
    return f'  const DAILY_PAGES = {json_str};'


def render_daily_call(data):
    json_str = json.dumps(dict(sorted(data.items())), separators=(',', ':'))
    return f'  const DAILY_CALL = {json_str};'


def render_page_totals(totals):
    body = ', '.join(f'{k}: {totals[k]}' for k in PAGE_KEYS)
    return f'  const PAGE_TOTALS = {{ {body} }};'


def render_call_total(total):
    return f"  const CALL_TOTAL = {{ activeUsers: {total['activeUsers']}, eventCount: {total['eventCount']} }};"


def render_daily_site(data):
    json_str = json.dumps(dict(sorted(data.items())), separators=(',', ':'))
    return f'  const DAILY_SITE = {json_str};'


def render_daily_subevents(data):
    ordered = {k: dict(sorted(data[k].items())) for k in EVENT_KEYS}
    json_str = json.dumps(ordered, separators=(',', ':'))
    return f'  const DAILY_SUBEVENTS = {json_str};'


def render_subevent_totals(totals):
    ordered = {k: totals[k] for k in EVENT_KEYS}
    json_str = json.dumps(ordered, separators=(',', ':'))
    return f'  const SUBEVENT_TOTALS = {json_str};'


def render_daily_first_user(data):
    ordered = {k: dict(sorted(data[k].items())) for k in GROUP_KEYS}
    json_str = json.dumps(ordered, separators=(',', ':'))
    return f'  const DAILY_FIRST_USER = {json_str};'


def render_first_user_totals(totals):
    body = ', '.join(f'{k}: {totals[k]}' for k in GROUP_KEYS)
    return f'  const FIRST_USER_TOTALS = {{ {body} }};'


def patch_scalars(src, new_from, new_to, generated_at, new_site_total):
    src = re.sub(
        r'const SITE_ACTIVE_USERS_TOTAL = \d+;',
        f'const SITE_ACTIVE_USERS_TOTAL = {new_site_total};',
        src,
    )
    src = re.sub(
        r"const DATE_RANGE = \{ from: '[\d-]+', to: '[\d-]+' \};",
        f"const DATE_RANGE = {{ from: '{new_from}', to: '{new_to}' }};",
        src,
    )
    src = re.sub(r"const GENERATED_AT = '.*?';", f"const GENERATED_AT = '{generated_at}';", src)
    return src


def replace_block_text(src, old_start, old_end, new_text):
    return src[:old_start] + new_text + src[old_end:]


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--html', required=True)
    ap.add_argument('--indir', required=True)
    ap.add_argument('--generated-at', default=None)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--no-backup', action='store_true')
    args = ap.parse_args()

    with open(args.html, encoding='utf-8') as f:
        src = f.read()

    date_range = parse_scalars(src)

    _, _, daily_pages_body = extract_single_line_block(src, 'DAILY_PAGES')
    _, _, daily_call_body = extract_single_line_block(src, 'DAILY_CALL')
    _, _, page_totals_body = extract_single_line_block(src, 'PAGE_TOTALS')
    _, _, call_total_body = extract_single_line_block(src, 'CALL_TOTAL')
    _, _, daily_site_body = extract_single_line_block(src, 'DAILY_SITE')
    _, _, daily_subevents_body = extract_single_line_block(src, 'DAILY_SUBEVENTS')
    _, _, subevent_totals_body = extract_single_line_block(src, 'SUBEVENT_TOTALS')
    _, _, daily_first_user_body = extract_single_line_block(src, 'DAILY_FIRST_USER')

    old_daily_pages = parse_daily_pages(daily_pages_body)
    old_daily_call = parse_daily_call(daily_call_body)
    old_daily_site = parse_daily_site(daily_site_body)
    old_daily_subevents = parse_daily_subevents(daily_subevents_body)
    old_daily_first_user = parse_daily_first_user(daily_first_user_body)

    incr_pages, incoming_page_dates = load_pages_incremental(args.indir)
    incr_call, incoming_call_dates = load_call_incremental(args.indir)
    incoming_dates = sorted(set(incoming_page_dates) | set(incoming_call_dates))

    if not incoming_dates:
        raise SafetyError('신규 데이터가 없습니다.')

    new_to = max(incoming_dates)
    new_from = (date.fromisoformat(new_to) - timedelta(days=WINDOW_DAYS - 1)).isoformat()

    new_daily_pages = {k: merge_and_slide(old_daily_pages.get(k, {}), incr_pages.get(k, {}), new_from, new_to) for k in PAGE_KEYS}
    new_daily_call = merge_and_slide(old_daily_call, incr_call, new_from, new_to)

    new_page_totals = load_pages_period(args.indir)
    new_call_total = load_call_period(args.indir)

    incr_site, _ = load_site_incremental(args.indir)
    new_daily_site = merge_and_slide(old_daily_site, incr_site, new_from, new_to)
    new_site_total = load_site_period(args.indir)

    incr_subevents, _ = load_subevents_incremental(args.indir)
    new_daily_subevents = {k: merge_and_slide(old_daily_subevents.get(k, {}), incr_subevents.get(k, {}), new_from, new_to) for k in EVENT_KEYS}
    new_subevent_totals = load_subevents_period(args.indir)

    incr_first_user, _, first_user_incr_warnings = load_firstuser_incremental(args.indir)
    new_daily_first_user = {k: merge_and_slide(old_daily_first_user.get(k, {}), incr_first_user.get(k, {}), new_from, new_to) for k in GROUP_KEYS}
    new_first_user_totals, first_user_period_warnings = load_firstuser_period(args.indir)

    warnings = validate(
        new_daily_pages, new_page_totals, new_daily_call, new_call_total,
        new_daily_site, new_site_total, new_daily_subevents, new_subevent_totals,
        new_daily_first_user, new_first_user_totals,
        new_from, new_to,
    )
    warnings = first_user_incr_warnings + first_user_period_warnings + warnings

    generated_at = args.generated_at or datetime.now(timezone.utc).strftime(GENERATED_AT_FMT)

    new_src = src
    s, e, _ = extract_single_line_block(new_src, 'DAILY_PAGES')
    new_src = replace_block_text(new_src, s, e, render_daily_pages(new_daily_pages))
    s, e, _ = extract_single_line_block(new_src, 'DAILY_CALL')
    new_src = replace_block_text(new_src, s, e, render_daily_call(new_daily_call))
    s, e, _ = extract_single_line_block(new_src, 'PAGE_TOTALS')
    new_src = replace_block_text(new_src, s, e, render_page_totals(new_page_totals))
    s, e, _ = extract_single_line_block(new_src, 'CALL_TOTAL')
    new_src = replace_block_text(new_src, s, e, render_call_total(new_call_total))
    s, e, _ = extract_single_line_block(new_src, 'DAILY_SITE')
    new_src = replace_block_text(new_src, s, e, render_daily_site(new_daily_site))
    s, e, _ = extract_single_line_block(new_src, 'DAILY_SUBEVENTS')
    new_src = replace_block_text(new_src, s, e, render_daily_subevents(new_daily_subevents))
    s, e, _ = extract_single_line_block(new_src, 'SUBEVENT_TOTALS')
    new_src = replace_block_text(new_src, s, e, render_subevent_totals(new_subevent_totals))
    s, e, _ = extract_single_line_block(new_src, 'DAILY_FIRST_USER')
    new_src = replace_block_text(new_src, s, e, render_daily_first_user(new_daily_first_user))
    s, e, _ = extract_single_line_block(new_src, 'FIRST_USER_TOTALS')
    new_src = replace_block_text(new_src, s, e, render_first_user_totals(new_first_user_totals))
    new_src = patch_scalars(new_src, new_from, new_to, generated_at, new_site_total)

    # --- 스모크 테스트: 재작성한 소스를 다시 파싱해 라운드트립 일치 확인 ---
    _, _, chk = extract_single_line_block(new_src, 'DAILY_PAGES')
    assert parse_daily_pages(chk) == new_daily_pages
    _, _, chk = extract_single_line_block(new_src, 'DAILY_CALL')
    assert parse_daily_call(chk) == new_daily_call
    _, _, chk = extract_single_line_block(new_src, 'PAGE_TOTALS')
    assert parse_js_number_object(chk) == new_page_totals
    _, _, chk = extract_single_line_block(new_src, 'DAILY_SITE')
    assert parse_daily_site(chk) == new_daily_site
    _, _, chk = extract_single_line_block(new_src, 'DAILY_SUBEVENTS')
    assert parse_daily_subevents(chk) == new_daily_subevents
    _, _, chk = extract_single_line_block(new_src, 'SUBEVENT_TOTALS')
    assert parse_subevent_totals(chk) == new_subevent_totals
    _, _, chk = extract_single_line_block(new_src, 'DAILY_FIRST_USER')
    assert parse_daily_first_user(chk) == new_daily_first_user
    _, _, chk = extract_single_line_block(new_src, 'FIRST_USER_TOTALS')
    assert parse_js_number_object(chk) == new_first_user_totals
    assert parse_site_total(new_src) == new_site_total
    chk_range = parse_scalars(new_src)
    assert chk_range == {'from': new_from, 'to': new_to}

    print('=== update_ga4_unsedang.py 요약 ===')
    print(f'윈도우: {date_range["from"]}~{date_range["to"]} -> {new_from}~{new_to} ({WINDOW_DAYS}일 유지, 롤링)')
    print(f'PAGE_TOTALS(기간 합계, 활성사용자): {new_page_totals}')
    print(f'CALL_TOTAL(기간 합계): {new_call_total}')
    print(f'SITE_ACTIVE_USERS_TOTAL(기간 합계): {new_site_total}')
    print(f'SUBEVENT_TOTALS(기간 합계): {new_subevent_totals}')
    print(f'FIRST_USER_TOTALS(기간 합계): {new_first_user_totals}')
    if warnings:
        print('경고:')
        for w in warnings:
            print(f'  - {w}')
    else:
        print('경고: (없음)')

    if args.dry_run:
        print('\n--dry-run 이므로 파일을 쓰지 않았습니다.')
        return

    if not args.no_backup:
        ts = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
        backup_path = f'{args.html}.bak-{ts}'
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(src)
        print(f'백업: {backup_path}')

    dir_ = os.path.dirname(os.path.abspath(args.html))
    fd, tmp_path = tempfile.mkstemp(dir=dir_, prefix='.ga4-funnel-', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(new_src)
        os.replace(tmp_path, args.html)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise

    print(f'완료: {args.html} 갱신됨')


if __name__ == '__main__':
    try:
        main()
    except SafetyError as e:
        print(f'\n[SafetyError] {e}', file=sys.stderr)
        sys.exit(1)
