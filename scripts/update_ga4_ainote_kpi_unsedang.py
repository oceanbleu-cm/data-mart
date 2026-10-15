#!/usr/bin/env python3
"""
운세당 AI 상담노트 화면별 KPI 리포트(html/ga4-ainote-kpi-unsedang.html) 업데이트 스크립트.

`html/ga4-funnel-unsedang.html`과 같은 철학 — **누적 성장형**(기존 날짜 절대 불변, 새 날짜만
추가, 끝에서 밀어내지 않음)이다. `html/ga4-channel-unsedang.html`(최근 14일 롤링)과는 다르다.
AI 상담노트 기능 집계 시작일(2026-09-30)이 고정 시작점이고, 매 실행마다 D-1까지 날짜가 늘어난다.

이 리포트는 데이터 출처가 두 종류다:
  1) GA4 BigQuery export(`unsedang.analytics_488612198`, 2026-10-15에 Supermetrics MCP에서
     전환 — docs/bigquery-ga4-mapping.md 참고) — CALL/PRETEL/PAGES(aiNote·noteInfo)/
     SUBEVENTS(7종)/ENGAGEMENT/UTM_CLICK. activeUsers는 비집계 지표라, 이 스크립트는
     BigQuery를 직접 호출하지 않는다(에이전트만 BigQuery MCP 툴 호출 가능) —
     `.claude/commands/update-ga4-ainote-kpi-unsedang.md`가 `scripts/sql/*.sql`을 읽어 조회한
     결과를 미리 JSON 파일로 떠서 `--indir`에 넣어두면 이 스크립트가 읽는다. 기간 합계는
     "새 날짜만 반영"이 아니라 **매번 전체 누적 기간을 재조회한 값으로 통째로 교체**한다.
     윈도우 시작일(2026-09-30)이 BQ export 시작일(2026-08-27)보다 항상 뒤라 클램프 불필요.
  2) 운세당 DB API(consultation-stats/monthly) — ALIMTALK/AINOTE_CONSULT_CNT/
     AINOTE_CONSULT_USR/AINOTE_REPEAT_USR/AINOTE_REPEAT_CNT/AINOTE_AFTER_REPEAT_CNT(전부
     선불 전용, 후불은 항상 0). 이 API는 인증 없는
     공개 CORS API라(html/db-data-unsedang.html 등 기존 코드에서 브라우저가 직접 fetch하는
     선례 확인됨) 이 스크립트가 **직접 호출**한다 — 별도 JSON 스테이징 불필요. 월 단위
     (baseMonth)로만 조회 가능해 기간이 두 달에 걸치면 두 번 호출해 날짜별 dailyStats를
     모은다. 건수(aiNoteAlimtalkCount/consultationCount)는 집계 가능 지표라 일별 합산이
     정확하지만, 유저수(userCount.*)는 날짜 간 중복제거가 보장되지 않는다는 API 자체 경고가
     있어(이 API는 임의 날짜범위 재조회를 지원하지 않아 exact 총합을 따로 얻을 방법이 없음)
     이 스크립트도 기존 리포트와 동일하게 "일별 합산 근사값"을 그대로 쓴다.

**DAILY_AINOTE_USAGE는 이 스크립트가 절대 건드리지 않는다** — 운영진이 직접 전달하는 수동
실집계(자동 수집 경로 없음, html 파일 자체 주석에도 명시돼 있음). 새 날짜가 생겨도 이
딕셔너리에 값이 없으면 보조지표(aux, 목표 없음)라 0으로 표시될 뿐 판정에 영향 없다.

사용법:
    python3 update_ga4_ainote_kpi_unsedang.py --html <path> --indir <tmpdir> [--dry-run]
                                               [--generated-at STR] [--no-backup] [--skip-db]
    python3 update_ga4_ainote_kpi_unsedang.py --html <path> --db-only [--to YYYY-MM-DD]
                                               [--dry-run] [--generated-at STR] [--no-backup]

`--db-only`: GA4 쪽(DATE_RANGE 포함)은 전혀 건드리지 않고 DB API 쪽 6개 지표
(ALIMTALK/AINOTE_CONSULT_CNT/AINOTE_CONSULT_USR/AINOTE_REPEAT_USR/AINOTE_REPEAT_CNT/
AINOTE_AFTER_REPEAT_CNT)만 START_DATE~(--to 또는 기존 DATE_RANGE.to)로 다시 조회해 채운다.
직전 실행이 DB API 장애로 `--skip-db`를 썼을 때 GA4 쪽은 이미 최신이라 일반 증분 실행으로는
재시도 트리거가 안 걸리는 경우(증분 GA4 신규 날짜가 없어 조기 종료됨)를 메우기 위한
땜빵용 모드다 — `--indir` 불필요.

입력 디렉터리(--indir) 안의 GA4 JSON 파일 12개:
    call_incremental.json / call_period.json
        {"rows":[{"date","activeUsers"}]} / {"rows":[{"activeUsers"}]}  (한 행)
        (eventName IN (pre_tel_click, post_tel_click), dimension은 date만 — eventName을
         dimension에 넣지 말 것(중복 집계 방지). period는 dimension 전체 제거, 새 누적기간
         전체 재조회.)
    pretel_incremental.json / pretel_period.json
        위와 동일 스키마, 단 filter는 eventName = pre_tel_click 만.
    pages_incremental.json / pages_period.json
        {"rows":[{"date","path","activeUsers"}]} / {"rows":[{"path","activeUsers"}]}
        (path IN ('/view/ai-note','/view/ai-note/noteInfo'). incremental은 dimension
         date+path, period는 path만(date 제거).)
    subevents_incremental.json / subevents_period.json
        {"rows":[{"date","eventName","activeUsers"}]} / {"rows":[{"eventName","activeUsers"}]}
        (eventName IN SUBEVENT_KEYS 7개. incremental은 date+eventName, period는 eventName만.)
    engagement_incremental.json / engagement_period.json
        {"rows":[{"date","totalEngagementDuration","activeUsers"}]} /
        {"rows":[{"totalEngagementDuration","activeUsers"}]} (한 행)
        (path = '/view/ai-note/noteInfo' 필터, dimension은 incremental은 date만, period는
         dimension 전체 제거.)
    utmclick_incremental.json / utmclick_period.json
        {"rows":[{"date","activeUsers"}]} / {"rows":[{"activeUsers"}]} (한 행)
        (utm_source=kakao_alimtalk AND utm_medium=push AND utm_campaign=callnote_created 필터.)
    recoclick_incremental.json / recoclick_period.json
        {"rows":[{"date","activeUsers"}]} / {"rows":[{"activeUsers"}]} (한 행)
        (선생님 추천 버튼 클릭 — eventName이 callnote_reco_click_{선생님번호}로 선생님마다 달라져
         정확히 일치하는 이름이 없다. eventName =@ 'callnote_reco_click' (contains)로 전체
         선생님번호를 합산해 하나의 지표로 집계한다.)

DB 쪽(ALIMTALK/AINOTE_CONSULT_CNT/AINOTE_CONSULT_USR/AINOTE_REPEAT_USR/AINOTE_REPEAT_CNT/
AINOTE_AFTER_REPEAT_CNT)은 파일 스테이징이
필요 없다 — 이 스크립트가 adm.unsedang.com을 직접 호출한다. 네트워크 접근이 없는 환경(또는
이미 별도로 처리했을 때)은 `--skip-db`로 DB 쪽 갱신을 건너뛸 수 있다.
"""
import argparse
import json
import os
import re
import sys
import tempfile
import urllib.request
import urllib.error
from datetime import date, datetime, timedelta, timezone

START_DATE = '2026-09-30'  # AI 상담노트 집계 시작일 — 이 이전 날짜는 담지 않는다(고정 시작점).

SUBEVENT_KEYS = [
    'ai-note-agree-pop',
    'ai-note-agree-click',
    'ai-note-cancel-click',
    'ai-note-review-skip',
    'ai-note-review-next',
    'ai-note-review-submit',
    'ai-note-councel-click',
]

PAGE_PATH_TO_KEY = {
    '/view/ai-note': 'DAILY_AINOTE',
    '/view/ai-note/noteInfo': 'DAILY_NOTEINFO',
}

DB_API_TEMPLATE = 'https://adm.unsedang.com/api/v1/reports/consultation-stats/monthly?baseMonth={month}'

GENERATED_AT_FMT = '%Y-%m-%d %H:%M UTC (BigQuery GA4 export analytics_488612198 + 운세당 DB API 조회, 정적 스냅샷)'


class SafetyError(Exception):
    """검증 실패 — 원본 파일은 절대 건드리지 않고 여기서 중단."""


# ---------------------------------------------------------------------------
# 0. 날짜 유틸
# ---------------------------------------------------------------------------

def window_dates(d_from, d_to):
    d0 = date.fromisoformat(d_from)
    d1 = date.fromisoformat(d_to)
    return [(d0 + timedelta(days=i)).isoformat() for i in range((d1 - d0).days + 1)]


def months_between(d_from, d_to):
    """[d_from, d_to]가 걸치는 YYYY-MM 목록(baseMonth 조회용)."""
    d0 = date.fromisoformat(d_from).replace(day=1)
    d1 = date.fromisoformat(d_to).replace(day=1)
    months = []
    cur = d0
    while cur <= d1:
        months.append(cur.strftime('%Y-%m'))
        if cur.month == 12:
            cur = cur.replace(year=cur.year + 1, month=1)
        else:
            cur = cur.replace(month=cur.month + 1)
    return months


# ---------------------------------------------------------------------------
# 1. HTML 파싱 — 전부 `  const NAME = {...};` 한 줄 블록(SUBEVENTS류 제외)
# ---------------------------------------------------------------------------

def extract_single_line_block(src, name):
    # 줄 끝에 `// 주석`이 붙는 경우(PAGE_TOTALS, ENGAGEMENT_TOTAL 등)가 있어 `$` 앵커 대신
    # `;`까지만 매치하고 그 뒤 내용은 신경 쓰지 않는다. 매치 구간(m.start~m.end)은 `;`까지만
    # 포함하므로 trailing comment는 replace_block_text에서 그대로 보존된다.
    pattern = re.compile(r'^  const ' + re.escape(name) + r' = (\{.*?\});', re.M)
    m = pattern.search(src)
    if not m:
        raise SafetyError(f'{name} 블록을 찾지 못했습니다 — HTML 구조가 바뀐 것 같습니다. 수동 확인 필요.')
    return m.start(), m.end(), m.group(1)


def extract_multi_line_block(src, name):
    pattern = re.compile(r'^  const ' + re.escape(name) + r' = \{\n(.*?)\n  \};$', re.M | re.S)
    m = pattern.search(src)
    if not m:
        raise SafetyError(f'{name} 블록을 찾지 못했습니다 — HTML 구조가 바뀐 것 같습니다. 수동 확인 필요.')
    return m.start(), m.end(), m.group(1)


def extract_scalar(src, name):
    m = re.search(r'const ' + re.escape(name) + r' = (-?\d+);', src)
    if not m:
        raise SafetyError(f'{name} 스칼라를 찾지 못했습니다.')
    return m.start(), m.end(), int(m.group(1))


def parse_flat_dict(body):
    return json.loads(body)


def parse_js_number_object(body):
    out = {}
    for m in re.finditer(r'(\w+):\s*(-?\d+)', body):
        out[m.group(1)] = int(m.group(2))
    return out


def parse_scalars(src):
    m = re.search(r"const DATE_RANGE = \{ from: '([\d-]+)', to: '([\d-]+)' \};", src)
    if not m:
        raise SafetyError('DATE_RANGE 상수를 찾지 못했습니다.')
    return {'from': m.group(1), 'to': m.group(2)}


# ---------------------------------------------------------------------------
# 2. GA4 증분/기간 JSON 로드 (에이전트가 --indir에 미리 떠둔 파일)
# ---------------------------------------------------------------------------

def _read_rows(indir, fname, required=True):
    path = os.path.join(indir, fname)
    if not os.path.exists(path):
        if required:
            raise SafetyError(f'{indir}에 {fname}이 없습니다.')
        return []
    with open(path, encoding='utf-8') as f:
        return json.load(f).get('rows', [])


def load_flat_incremental(indir, fname):
    """{"rows":[{"date","activeUsers"}]} -> {date: activeUsers}."""
    rows = _read_rows(indir, fname)
    return {r['date']: (r['activeUsers'] or 0) for r in rows}


def load_flat_period(indir, fname):
    rows = _read_rows(indir, fname)
    if not rows:
        raise SafetyError(f'{fname}에 결과 행이 없습니다 — GA4 쿼리가 비정상일 가능성이 있습니다.')
    return rows[0]['activeUsers'] or 0


def load_pages_incremental(indir):
    rows = _read_rows(indir, 'pages_incremental.json')
    out = {'DAILY_AINOTE': {}, 'DAILY_NOTEINFO': {}}
    for r in rows:
        key = PAGE_PATH_TO_KEY.get(r['path'])
        if key is None:
            raise SafetyError(
                f"알 수 없는 페이지 경로: {r['path']!r} — pages_incremental.json은 "
                f"'/view/ai-note'와 '/view/ai-note/noteInfo'만 포함해야 합니다."
            )
        out[key][r['date']] = r['activeUsers'] or 0
    return out


def load_pages_period(indir):
    rows = _read_rows(indir, 'pages_period.json')
    totals = {'aiNote': 0, 'noteInfo': 0}
    key_to_short = {'DAILY_AINOTE': 'aiNote', 'DAILY_NOTEINFO': 'noteInfo'}
    for r in rows:
        key = PAGE_PATH_TO_KEY.get(r['path'])
        if key is None:
            raise SafetyError(f"pages_period.json: 알 수 없는 페이지 경로 {r['path']!r}")
        totals[key_to_short[key]] = r['activeUsers'] or 0
    return totals


def load_subevents_incremental(indir):
    rows = _read_rows(indir, 'subevents_incremental.json')
    incr = {k: {} for k in SUBEVENT_KEYS}
    for r in rows:
        if r['eventName'] not in incr:
            raise SafetyError(
                f"알 수 없는 subevent eventName: {r['eventName']!r} — SUBEVENT_KEYS에 없는 "
                f'신규 이벤트입니다. 의도적 추가라면 스크립트의 SUBEVENT_KEYS와 HTML을 먼저 '
                f'함께 갱신하세요.'
            )
        incr[r['eventName']][r['date']] = r['activeUsers'] or 0
    return incr


def load_subevents_period(indir):
    rows = _read_rows(indir, 'subevents_period.json')
    totals = {k: 0 for k in SUBEVENT_KEYS}
    for r in rows:
        if r['eventName'] not in totals:
            raise SafetyError(f"subevents_period.json: 알 수 없는 eventName {r['eventName']!r}")
        totals[r['eventName']] = r['activeUsers'] or 0
    return totals


def load_engagement_incremental(indir):
    rows = _read_rows(indir, 'engagement_incremental.json')
    return {r['date']: [r['totalEngagementDuration'] or 0, r['activeUsers'] or 0] for r in rows}


def load_engagement_period(indir):
    rows = _read_rows(indir, 'engagement_period.json')
    if not rows:
        raise SafetyError('engagement_period.json에 결과 행이 없습니다.')
    r = rows[0]
    return {'duration': r['totalEngagementDuration'] or 0, 'users': r['activeUsers'] or 0}


# ---------------------------------------------------------------------------
# 3. DB API 직접 호출 (공개 CORS API, 인증 불필요)
# ---------------------------------------------------------------------------

def fetch_db_daily(d_from, d_to, timeout=15):
    """[d_from, d_to] 구간에 걸치는 baseMonth들을 조회해 날짜별
    {alimtalk, consultCnt, consultUsr, repeatUsr, repeatCnt, afterRepeatCnt} 딕셔너리로
    반환한다(선불 전용 필드만 추출). postpaid 쪽 aiNoteConsultation류·aiNoteRepeatConsultation은
    AI상담노트가 선불 전용 기능이라 집계하지 않는다(항상 0 — API 응답으로 확인됨). 단,
    afterAiNoteRepeatConsultation(알림톡을 받은 뒤 "아무" 재상담, AI노트 생성 여부 무관)은
    postpaid에도 값이 존재함(2026-09-30~2026-10-11 기준 23건 확인) — 리포트 전체가
    "AI상담노트=선불 전용" 원칙을 따르기로 사용자가 확정해 의도적으로 선불만 쓴다."""
    daily = {}
    for month in months_between(d_from, d_to):
        url = DB_API_TEMPLATE.format(month=month)
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                if resp.status != 200:
                    raise SafetyError(f'DB API 응답 실패({month}): HTTP {resp.status}')
                payload = json.loads(resp.read().decode('utf-8'))
        except urllib.error.URLError as e:
            raise SafetyError(f'DB API 호출 실패({month}): {e}')
        for day in payload.get('dailyStats', []):
            d = day['date']
            if d < d_from or d > d_to:
                continue
            prepaid_cc = day['consultationCount']['prepaid']
            prepaid_uc = day['userCount']['prepaid']
            daily[d] = {
                'alimtalk': day.get('aiNoteAlimtalkCount', 0) or 0,
                'consultCnt': prepaid_cc.get('aiNoteConsultation', 0) or 0,
                'consultUsr': prepaid_uc.get('aiNoteConsultation', 0) or 0,
                'repeatUsr': prepaid_uc.get('aiNoteRepeatConsultation', 0) or 0,
                'repeatCnt': prepaid_cc.get('aiNoteRepeatConsultation', 0) or 0,
                'afterRepeatCnt': prepaid_cc.get('afterAiNoteRepeatConsultation', 0) or 0,
            }
    return daily


# ---------------------------------------------------------------------------
# 4. 병합(누적 — 기존 날짜 유지, 새 날짜 추가, 밀어내지 않음)
# ---------------------------------------------------------------------------

def merge_cumulative(old_series, incr_series):
    """old_series를 기준으로 incr_series 값을 덮어써서 병합한다(최근 며칠은 GA4 재확정으로
    값이 바뀔 수 있어 덮어쓰기 허용). 끝에서 밀어내는 로직 없음 — START_DATE부터 전부 유지."""
    combined = dict(old_series)
    combined.update(incr_series)
    return dict(sorted(combined.items()))


# ---------------------------------------------------------------------------
# 5. 검증
# ---------------------------------------------------------------------------

def validate_flat(label, daily, total, new_from, new_to, check_period_range=True):
    warnings = []
    for d, v in daily.items():
        if d < START_DATE or d > new_to:
            raise SafetyError(f'G-WINDOW 위반: {label} {d}가 유효 범위({START_DATE}~{new_to}) 밖입니다.')
        if v < 0:
            raise SafetyError(f'G6 위반: {label} {d} 값이 음수입니다 ({v})')
    if total < 0:
        raise SafetyError(f'G6 위반: {label}_TOTAL이 음수입니다.')
    if check_period_range:
        day_vals = list(daily.values())
        if day_vals:
            day_sum, day_max = sum(day_vals), max(day_vals)
            if not (day_max <= total <= day_sum):
                warnings.append(
                    f'{label}_TOTAL={total}가 일별 값 범위 [{day_max}, {day_sum}] 밖입니다 — '
                    f'재조회 결과를 확인하세요(경고만, 중단하지 않음).'
                )
    expected = set(window_dates(new_from, new_to))
    missing = expected - set(daily)
    if missing:
        warnings.append(f'{label}에 누락된 날짜: {sorted(missing)[:5]}... (GA4/DB가 0으로 응답했거나 쿼리 범위 확인 필요)')
    return warnings


# ---------------------------------------------------------------------------
# 6. 재직렬화
# ---------------------------------------------------------------------------

def render_flat(name, data):
    return f'  const {name} = {json.dumps(dict(sorted(data.items())), separators=(",", ":"))};'


def render_subevents_block(name, data):
    lines = [f'  const {name} = {{']
    for i, key in enumerate(SUBEVENT_KEYS):
        json_str = json.dumps(dict(sorted(data[key].items())), separators=(',', ':'))
        comma = ',' if i < len(SUBEVENT_KEYS) - 1 else ''
        lines.append(f'    "{key}": {json_str}{comma}')
    lines.append('  };')
    return '\n'.join(lines)


def render_subevent_totals(totals):
    parts = ', '.join(f'"{k}": {totals[k]}' for k in SUBEVENT_KEYS)
    return f'  const SUBEVENT_TOTALS = {{\n    {parts}\n  }};'


def render_engagement_block(data):
    json_str = json.dumps(dict(sorted(data.items())), separators=(',', ':'))
    return f'  const DAILY_ENGAGEMENT = {{\n    {json_str[1:-1]}\n  }};'


def patch_scalar(src, name, value):
    return re.sub(r'const ' + re.escape(name) + r' = -?\d+;', f'const {name} = {value};', src)


def patch_js_object_literal(src, name, mapping):
    body = ', '.join(f'{k}: {v}' for k, v in mapping.items())
    return re.sub(
        r'const ' + re.escape(name) + r' = \{[^{}]*\};',
        f'const {name} = {{ {body} }};',
        src,
    )


def patch_date_range(src, new_from, new_to):
    return re.sub(
        r"const DATE_RANGE = \{ from: '[\d-]+', to: '[\d-]+' \};",
        f"const DATE_RANGE = {{ from: '{new_from}', to: '{new_to}' }};",
        src,
    )


def patch_generated_at(src, generated_at):
    return re.sub(r"const GENERATED_AT = '.*?';", f"const GENERATED_AT = '{generated_at}';", src)


def replace_block_text(src, old_start, old_end, new_text):
    return src[:old_start] + new_text + src[old_end:]


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

FLAT_SERIES = [
    # (daily_const, total_const, file_prefix, source)
    ('DAILY_CALL', 'CALL_TOTAL', 'call', 'ga4'),
    ('DAILY_PRETEL', 'PRETEL_TOTAL', 'pretel', 'ga4'),
    ('DAILY_UTM_CLICK', 'UTM_CLICK_TOTAL', 'utmclick', 'ga4'),
    ('DAILY_RECO_CLICK', 'RECO_CLICK_TOTAL', 'recoclick', 'ga4'),
    ('DAILY_ALIMTALK', 'ALIMTALK_TOTAL', None, 'db'),
    ('DAILY_AINOTE_CONSULT_CNT', 'AINOTE_CONSULT_CNT_TOTAL', None, 'db'),
    ('DAILY_AINOTE_CONSULT_USR', 'AINOTE_CONSULT_USR_TOTAL', None, 'db'),
    ('DAILY_AINOTE_REPEAT_USR', 'AINOTE_REPEAT_USR_TOTAL', None, 'db'),
    ('DAILY_AINOTE_REPEAT_CNT', 'AINOTE_REPEAT_CNT_TOTAL', None, 'db'),
    ('DAILY_AINOTE_AFTER_REPEAT_CNT', 'AINOTE_AFTER_REPEAT_CNT_TOTAL', None, 'db'),
]

DB_FIELD_MAP = {
    'DAILY_ALIMTALK': 'alimtalk',
    'DAILY_AINOTE_CONSULT_CNT': 'consultCnt',
    'DAILY_AINOTE_CONSULT_USR': 'consultUsr',
    'DAILY_AINOTE_REPEAT_USR': 'repeatUsr',
    'DAILY_AINOTE_REPEAT_CNT': 'repeatCnt',
    'DAILY_AINOTE_AFTER_REPEAT_CNT': 'afterRepeatCnt',
}


def db_only_main(args, src, date_range, old_daily):
    """GA4/DATE_RANGE는 그대로 두고 DB API 6개 지표만 START_DATE~new_to로 재조회해 채운다."""
    new_to = args.to or date_range['to']
    new_from = START_DATE
    if date.fromisoformat(new_to) > date.fromisoformat(date_range['to']):
        raise SafetyError(
            f'--db-only에서 --to({new_to})가 기존 DATE_RANGE.to({date_range["to"]})보다 미래입니다 — '
            'DB만 GA4보다 앞서갈 수 없습니다. GA4도 같이 갱신하려면 --db-only 없이 일반 모드로 실행하세요.'
        )

    db_daily = fetch_db_daily(new_from, new_to)
    new_daily = {}
    new_total = {}
    for daily_name, field in DB_FIELD_MAP.items():
        merged = dict(old_daily[daily_name])
        for d, rec in db_daily.items():
            merged[d] = rec[field]
        new_daily[daily_name] = dict(sorted(merged.items()))

    total_name_map = {name: total for name, total, _prefix, src_ in FLAT_SERIES if src_ == 'db'}
    for daily_name, total_name in total_name_map.items():
        new_total[total_name] = sum(new_daily[daily_name].values())

    warnings = []
    missing_db_dates = set(window_dates(new_from, new_to)) - set(db_daily)
    if missing_db_dates:
        warnings.append(f'DB API dailyStats에 누락된 날짜: {sorted(missing_db_dates)[:5]}...')
    for daily_name, total_name in total_name_map.items():
        warnings += validate_flat(daily_name, new_daily[daily_name], new_total[total_name], new_from, new_to,
                                   check_period_range=False)

    generated_at = args.generated_at or datetime.now(timezone.utc).strftime(GENERATED_AT_FMT)

    new_src = src
    for daily_name, total_name in total_name_map.items():
        s, e, _ = extract_single_line_block(new_src, daily_name)
        new_src = replace_block_text(new_src, s, e, render_flat(daily_name, new_daily[daily_name]))
        new_src = patch_scalar(new_src, total_name, new_total[total_name])
    new_src = patch_generated_at(new_src, generated_at)

    # --- 스모크 테스트 ---
    for daily_name, total_name in total_name_map.items():
        _, _, chk = extract_single_line_block(new_src, daily_name)
        assert parse_flat_dict(chk) == new_daily[daily_name]
        assert extract_scalar(new_src, total_name)[2] == new_total[total_name]
    assert parse_scalars(new_src) == date_range  # DATE_RANGE 불변 확인

    print('=== update_ga4_ainote_kpi_unsedang.py --db-only 요약 ===')
    print(f'DB 재조회 범위: {new_from}~{new_to} (GA4/DATE_RANGE는 변경 없음: {date_range["from"]}~{date_range["to"]})')
    print(f'ALIMTALK/AINOTE_CONSULT_CNT/CONSULT_USR/REPEAT_USR/REPEAT_CNT/AFTER_REPEAT_CNT 기간 합계: '
          f'{new_total["ALIMTALK_TOTAL"]}/{new_total["AINOTE_CONSULT_CNT_TOTAL"]}/'
          f'{new_total["AINOTE_CONSULT_USR_TOTAL"]}/{new_total["AINOTE_REPEAT_USR_TOTAL"]}/'
          f'{new_total["AINOTE_REPEAT_CNT_TOTAL"]}/{new_total["AINOTE_AFTER_REPEAT_CNT_TOTAL"]}')
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
    fd, tmp_path = tempfile.mkstemp(dir=dir_, prefix='.ga4-ainote-kpi-', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(new_src)
        os.replace(tmp_path, args.html)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise

    print(f'완료: {args.html} 갱신됨')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--html', required=True)
    ap.add_argument('--indir', default=None, help='GA4 증분/기간 JSON이 들어있는 디렉터리 (--db-only면 불필요)')
    ap.add_argument('--to', default=None, help='새 종료일(YYYY-MM-DD). 기본: GA4 증분 데이터의 최댓값(--db-only는 기존 DATE_RANGE.to)')
    ap.add_argument('--generated-at', default=None)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--no-backup', action='store_true')
    ap.add_argument('--skip-db', action='store_true', help='DB API 호출을 건너뛴다(네트워크 불가 시)')
    ap.add_argument('--db-only', action='store_true', help='GA4/DATE_RANGE는 건드리지 않고 DB API 6개 지표만 재조회해 채운다')
    args = ap.parse_args()

    if not args.db_only and not args.indir:
        ap.error('--indir은 --db-only가 아닌 한 필수입니다.')
    if args.db_only and args.skip_db:
        ap.error('--db-only와 --skip-db는 동시에 쓸 수 없습니다(할 일이 없어집니다).')

    with open(args.html, encoding='utf-8') as f:
        src = f.read()

    date_range = parse_scalars(src)

    # --- 기존 값 파싱 ---
    old_daily = {}
    old_total = {}
    for daily_name, total_name, _prefix, _src in FLAT_SERIES:
        _, _, body = extract_single_line_block(src, daily_name)
        old_daily[daily_name] = parse_flat_dict(body)
        old_total[total_name] = extract_scalar(src, total_name)[2]

    if args.db_only:
        db_only_main(args, src, date_range, old_daily)
        return

    _, _, pages_ai_body = extract_single_line_block(src, 'DAILY_AINOTE')
    _, _, pages_note_body = extract_single_line_block(src, 'DAILY_NOTEINFO')
    old_daily['DAILY_AINOTE'] = parse_flat_dict(pages_ai_body)
    old_daily['DAILY_NOTEINFO'] = parse_flat_dict(pages_note_body)
    _, _, page_totals_body = extract_single_line_block(src, 'PAGE_TOTALS')
    old_page_totals = parse_js_number_object(page_totals_body)

    _, _, subevents_body = extract_multi_line_block(src, 'DAILY_SUBEVENTS')
    old_subevents = parse_flat_dict('{' + subevents_body + '}')
    for k in SUBEVENT_KEYS:
        old_subevents.setdefault(k, {})
    _, _, subevent_totals_body = extract_multi_line_block(src, 'SUBEVENT_TOTALS')
    old_subevent_totals = parse_flat_dict('{' + subevent_totals_body + '}')
    for k in SUBEVENT_KEYS:
        old_subevent_totals.setdefault(k, 0)

    _, _, engagement_body = extract_multi_line_block(src, 'DAILY_ENGAGEMENT')
    old_engagement = parse_flat_dict('{' + engagement_body + '}')
    _, _, engagement_total_body = extract_single_line_block(src, 'ENGAGEMENT_TOTAL')
    old_engagement_total = parse_js_number_object(engagement_total_body)

    # --- GA4 증분 로드 ---
    incr_daily = {}
    for daily_name, total_name, prefix, source in FLAT_SERIES:
        if source != 'ga4':
            continue
        incr_daily[daily_name] = load_flat_incremental(args.indir, f'{prefix}_incremental.json')

    pages_incr = load_pages_incremental(args.indir)
    subevents_incr = load_subevents_incremental(args.indir)
    engagement_incr = load_engagement_incremental(args.indir)

    incoming_dates = sorted(set().union(
        *[set(d) for d in incr_daily.values()],
        set(pages_incr['DAILY_AINOTE']), set(pages_incr['DAILY_NOTEINFO']),
        *[set(d) for d in subevents_incr.values()],
        set(engagement_incr),
    ))
    if not incoming_dates and not args.to:
        raise SafetyError('신규 GA4 데이터가 없습니다(--to로 종료일을 강제 지정하지 않는 한 중단).')

    new_to = args.to or max(incoming_dates)
    new_from = START_DATE
    if new_to <= date_range['to'] and not incoming_dates:
        print(f'이미 최신 상태입니다(마지막 수록일 {date_range["to"]}).')
        return

    # --- 병합(누적) ---
    new_daily = {}
    for daily_name, total_name, prefix, source in FLAT_SERIES:
        if source == 'ga4':
            new_daily[daily_name] = merge_cumulative(old_daily[daily_name], incr_daily[daily_name])
        else:
            new_daily[daily_name] = old_daily[daily_name]  # DB 쪽은 아래에서 별도 처리

    new_daily['DAILY_AINOTE'] = merge_cumulative(old_daily['DAILY_AINOTE'], pages_incr['DAILY_AINOTE'])
    new_daily['DAILY_NOTEINFO'] = merge_cumulative(old_daily['DAILY_NOTEINFO'], pages_incr['DAILY_NOTEINFO'])
    new_subevents = {k: merge_cumulative(old_subevents.get(k, {}), subevents_incr.get(k, {})) for k in SUBEVENT_KEYS}
    new_engagement = merge_cumulative(old_engagement, engagement_incr)

    # --- GA4 기간 합계(매번 전체 재조회값으로 교체) ---
    new_total = dict(old_total)
    for daily_name, total_name, prefix, source in FLAT_SERIES:
        if source != 'ga4':
            continue
        new_total[total_name] = load_flat_period(args.indir, f'{prefix}_period.json')
    new_page_totals = load_pages_period(args.indir)
    new_subevent_totals = load_subevents_period(args.indir)
    new_engagement_total = load_engagement_period(args.indir)

    # --- DB API (직접 호출) ---
    db_warnings = []
    if not args.skip_db:
        db_daily = fetch_db_daily(new_from, new_to)
        for daily_name, field in DB_FIELD_MAP.items():
            merged = dict(old_daily[daily_name])
            for d, rec in db_daily.items():
                merged[d] = rec[field]
            new_daily[daily_name] = dict(sorted(merged.items()))
        for daily_name, total_name, _prefix, source in FLAT_SERIES:
            if source != 'db':
                continue
            new_total[total_name] = sum(new_daily[daily_name].values())
        missing_db_dates = set(window_dates(new_from, new_to)) - set(db_daily)
        if missing_db_dates:
            db_warnings.append(f'DB API dailyStats에 누락된 날짜: {sorted(missing_db_dates)[:5]}...')
    else:
        db_warnings.append('--skip-db 지정됨 — ALIMTALK/AINOTE_CONSULT_*/AINOTE_REPEAT_USR는 갱신하지 않았습니다.')

    # --- 검증 ---
    warnings = list(db_warnings)
    for daily_name, total_name, _prefix, source in FLAT_SERIES:
        warnings += validate_flat(daily_name, new_daily[daily_name], new_total[total_name], new_from, new_to,
                                   check_period_range=(source == 'ga4'))
    warnings += validate_flat('DAILY_AINOTE', new_daily['DAILY_AINOTE'], new_page_totals['aiNote'], new_from, new_to)
    warnings += validate_flat('DAILY_NOTEINFO', new_daily['DAILY_NOTEINFO'], new_page_totals['noteInfo'], new_from, new_to)
    for k in SUBEVENT_KEYS:
        warnings += validate_flat(f'DAILY_SUBEVENTS.{k}', new_subevents[k], new_subevent_totals[k], new_from, new_to)
    eng_users_daily = {d: v[1] for d, v in new_engagement.items()}
    warnings += validate_flat('DAILY_ENGAGEMENT(users)', eng_users_daily, new_engagement_total['users'], new_from, new_to)

    generated_at = args.generated_at or datetime.now(timezone.utc).strftime(GENERATED_AT_FMT)

    # --- 재작성 ---
    new_src = src
    for daily_name, total_name, _prefix, _source in FLAT_SERIES:
        s, e, _ = extract_single_line_block(new_src, daily_name)
        new_src = replace_block_text(new_src, s, e, render_flat(daily_name, new_daily[daily_name]))
        new_src = patch_scalar(new_src, total_name, new_total[total_name])

    s, e, _ = extract_single_line_block(new_src, 'DAILY_AINOTE')
    new_src = replace_block_text(new_src, s, e, render_flat('DAILY_AINOTE', new_daily['DAILY_AINOTE']))
    s, e, _ = extract_single_line_block(new_src, 'DAILY_NOTEINFO')
    new_src = replace_block_text(new_src, s, e, render_flat('DAILY_NOTEINFO', new_daily['DAILY_NOTEINFO']))
    new_src = patch_js_object_literal(new_src, 'PAGE_TOTALS', new_page_totals)

    s, e, _ = extract_multi_line_block(new_src, 'DAILY_SUBEVENTS')
    new_src = replace_block_text(new_src, s, e, render_subevents_block('DAILY_SUBEVENTS', new_subevents))
    s, e, _ = extract_multi_line_block(new_src, 'SUBEVENT_TOTALS')
    new_src = replace_block_text(new_src, s, e, render_subevent_totals(new_subevent_totals))

    s, e, _ = extract_multi_line_block(new_src, 'DAILY_ENGAGEMENT')
    new_src = replace_block_text(new_src, s, e, render_engagement_block(new_engagement))
    new_src = patch_js_object_literal(new_src, 'ENGAGEMENT_TOTAL', new_engagement_total)

    new_src = patch_date_range(new_src, new_from, new_to)
    new_src = patch_generated_at(new_src, generated_at)

    # --- 스모크 테스트 ---
    for daily_name, total_name, _prefix, _source in FLAT_SERIES:
        _, _, chk = extract_single_line_block(new_src, daily_name)
        assert parse_flat_dict(chk) == new_daily[daily_name]
        assert extract_scalar(new_src, total_name)[2] == new_total[total_name]
    _, _, chk = extract_single_line_block(new_src, 'DAILY_AINOTE')
    assert parse_flat_dict(chk) == new_daily['DAILY_AINOTE']
    _, _, chk = extract_single_line_block(new_src, 'DAILY_NOTEINFO')
    assert parse_flat_dict(chk) == new_daily['DAILY_NOTEINFO']
    _, _, chk = extract_single_line_block(new_src, 'PAGE_TOTALS')
    assert parse_js_number_object(chk) == new_page_totals
    _, _, chk = extract_multi_line_block(new_src, 'DAILY_SUBEVENTS')
    assert parse_flat_dict('{' + chk + '}') == new_subevents
    _, _, chk = extract_multi_line_block(new_src, 'SUBEVENT_TOTALS')
    assert parse_flat_dict('{' + chk + '}') == new_subevent_totals
    _, _, chk = extract_multi_line_block(new_src, 'DAILY_ENGAGEMENT')
    assert parse_flat_dict('{' + chk + '}') == new_engagement
    _, _, chk = extract_single_line_block(new_src, 'ENGAGEMENT_TOTAL')
    assert parse_js_number_object(chk) == new_engagement_total
    chk_range = parse_scalars(new_src)
    assert chk_range == {'from': new_from, 'to': new_to}

    print('=== update_ga4_ainote_kpi_unsedang.py 요약 ===')
    print(f'범위: {date_range["from"]}~{date_range["to"]} -> {new_from}~{new_to} (누적, {START_DATE}부터 고정)')
    print(f'CALL/PRETEL/UTM_CLICK 기간 합계: {new_total["CALL_TOTAL"]}/{new_total["PRETEL_TOTAL"]}/{new_total["UTM_CLICK_TOTAL"]}')
    print(f'PAGE_TOTALS: {new_page_totals}')
    print(f'SUBEVENT_TOTALS: {new_subevent_totals}')
    print(f'ENGAGEMENT_TOTAL: {new_engagement_total}')
    if not args.skip_db:
        print(f'ALIMTALK/AINOTE_CONSULT_CNT/CONSULT_USR/REPEAT_USR/REPEAT_CNT/AFTER_REPEAT_CNT 기간 합계: '
              f'{new_total["ALIMTALK_TOTAL"]}/{new_total["AINOTE_CONSULT_CNT_TOTAL"]}/'
              f'{new_total["AINOTE_CONSULT_USR_TOTAL"]}/{new_total["AINOTE_REPEAT_USR_TOTAL"]}/'
              f'{new_total["AINOTE_REPEAT_CNT_TOTAL"]}/{new_total["AINOTE_AFTER_REPEAT_CNT_TOTAL"]}')
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
    fd, tmp_path = tempfile.mkstemp(dir=dir_, prefix='.ga4-ainote-kpi-', suffix='.tmp')
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
