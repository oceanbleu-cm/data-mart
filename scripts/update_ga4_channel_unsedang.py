#!/usr/bin/env python3
"""
운세당 매체별 유입 리포트(html/ga4-channel-unsedang.html) 롤링-윈도우 업데이트 스크립트.

`html/ga4-funnel-unsedang.html`(퍼널 리포트)과는 갱신 철학이 다르다 — 그 리포트는
"기존 날짜 절대 불변, 새 날짜만 추가"하는 누적형이지만, 이 리포트는 헤더에 "최근 28일"이라고
명시된 **롤링(sliding) 윈도우**다. 그래서 매 실행마다:
  1) 새로 확정된 날짜(들)를 각 일별 시리즈에 추가하고
  2) 윈도우 밖으로 밀려난 오래된 날짜를 제거하고(윈도우 항상 28일 유지)
  3) 그룹별/기간 합계(FIRST_USER_TOTALS, TOTAL_PERIOD)는 "새 날짜만 반영"이 아니라
     **매번 새 윈도우 전체를 재조회한 값으로 통째로 교체**한다 — activeUsers는 비집계 지표라
     날짜를 밀어내고 더하는 방식으로는 정확한 값을 유지할 수 없기 때문이다.

이 스크립트는 Supermetrics를 직접 호출하지 않는다(에이전트만 MCP 툴 호출 가능).
`.claude/commands/update-ga4-channel-unsedang.md`가 미리 4개의 임시 JSON 파일을 만들어두면
이 스크립트가 그것을 읽어 HTML에 반영한다.

2026-09-30 리디자인(커밋 110c44a)으로 이 페이지의 "레퍼러 도메인 그룹"(sessionSource 기준,
REFERRER_DAILY/REFERRER_TOTALS/ETC_BREAKDOWN) 섹션이 삭제되고 "첫 사용자 소스 그룹"
(FIRST_USER_DAILY/FIRST_USER_TOTALS, GA4 firstUserSource 기준) 섹션만 남았다. 이 스크립트는
2026-10-01에 그 변경에 맞춰 레퍼러 섹션 관련 로직을 전부 제거했다(이전 버전은 git history
참고). firstUserSource는 사용자당 평생 하나뿐인 값이라 원본 값을 단순 합산해도 정확하다
(GA4도 이 dimension에는 필터 병합 재조회를 거부한다 — "summing deduplicated values" 에러).
TOTAL_DAILY/TOTAL_PERIOD(사이트 전체, attribution 기준과 무관)는 소스 필터 없이 별도로
재조회한 값이다.

사용법:
    python3 update_ga4_channel_unsedang.py --html <path> --indir <tmpdir> [--dry-run]
                                            [--generated-at STR] [--no-backup]

입력 디렉터리(--indir) 안의 6개 파일 스키마:
    total_daily.json     : {"rows": [{"date","activeUsers"}, ...]}
                            (소스 필터 없음, 마지막 수록일 다음날 ~ 새 to)
    total_period.json    : {"rows": [{"activeUsers"}]}  (한 행, 새 윈도우 전체, 소스 필터 없음)
    firstuser_raw_incremental.json : {"rows": [{"date","source","activeUsers","sessions"}, ...]}
                            (firstUserSource 기준, dimension 포함, 마지막 수록일 다음날 ~ 새 to.
                             그룹별 일별 값은 이 원본 행들을 FIRST_USER_LABEL_TO_GROUP으로
                             단순 합산해서 만든다 — 병합 필터 쿼리 불필요.)
    firstuser_raw_period.json : {"rows": [{"source","activeUsers","sessions"}, ...]}
                            (firstUserSource 기준, dimension 포함, 새 윈도우 전체. 그룹별
                             기간 합계도 마찬가지로 단순 합산해서 만든다.)
    recent7_total.json   : {"rows": [{"activeUsers"}]}  (한 행, 새 윈도우의 "최근 7일"만
                            — new_to-6~new_to, 소스 필터 없음. 표 중간에 삽입되는 "최근 7일
                            합계/평균" 행용. activeUsers는 비집계 지표라 TOTAL_DAILY 일별
                            값을 단순 합산할 수 없어 이 구간만 별도 재조회해야 한다.)
    recent7_firstuser_raw.json : {"rows": [{"source","activeUsers","sessions"}, ...]}
                            (firstUserSource 기준, dimension 포함, new_to-6~new_to만. 그룹별
                             "최근 7일" 합계도 마찬가지로 단순 합산해서 만든다.)

    알려진 매핑 테이블(FIRST_USER_LABEL_TO_GROUP)에 없는 새 firstUserSource 값이 나타나면
    더 이상 SafetyError로 중단하지 않는다 — classify_source()가 자동으로 분류한다:
    'naver' 포함(대소문자 무시) → naverGrp, 'google' 포함 → googleGrp, '(not set)'/''(빈 문자열)
    → notSet, 그 외 전부 → etcGrp. 자동 분류된 값은 "경고" 목록에 남아 사람이 사후 확인할 수
    있게 한다 — firstUserSource는 단순 합산이라 이 자동 분류만으로 즉시 정확하다(sessionSource
    처럼 병합 쿼리 필터에 별도로 포함시켜야 할 필요가 없다).
"""
import argparse
import json
import os
import re
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone

WINDOW_DAYS = 28

GROUP_KEYS = ['lg', 'notSet', 'direct', 'naverGrp', 'googleGrp', 'kakaoGrp', 'etcGrp']

# --- 알려진 GA4 원본 firstUserSource 값 ---
# ''(빈 문자열)은 GA4가 소스를 확인하지 못해 내려준 값 — '(not set)'과 동일하게 취급.
# kakaoGrp는 2026-10-01에 사용자 요청으로 신설 — 'kakao'가 포함된 값(카카오 로그인,
# 카카오 알림톡 등)을 더 이상 etcGrp에 묻지 않고 별도 그룹으로 추적한다.
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


GENERATED_AT_FMT = '%Y-%m-%d %H:%M UTC (Supermetrics GA4/GAWA 조회, 정적 스냅샷)'


class SafetyError(Exception):
    """검증 실패 — 원본 파일은 절대 건드리지 않고 여기서 중단."""


# ---------------------------------------------------------------------------
# 1. 기존 HTML 파싱
# ---------------------------------------------------------------------------

def extract_block(src, name, indent, open_ch='{', close_ch='}'):
    pattern = re.compile(
        r'^' + re.escape(indent) + r'const ' + re.escape(name) + r' = ' + re.escape(open_ch) + r'\n(.*?)\n'
        + re.escape(indent) + re.escape(close_ch) + r';$',
        re.M | re.S,
    )
    m = pattern.search(src)
    if not m:
        raise SafetyError(f'{name} 블록을 찾지 못했습니다 — HTML 구조가 바뀐 것 같습니다. 수동 확인 필요.')
    return m.start(), m.end(), m.group(1)


def parse_daily_block(body):
    """`  key: {json},` 형태의 (key -> {date:[u,s]}) 쌍을 줄바꿈/공백에 상관없이 전부 찾는다."""
    out = {}
    for m in re.finditer(r'(\w+):\s*(\{[^{}]*\}),', body):
        key, json_str = m.group(1), m.group(2)
        out[key] = json.loads(json_str)
    return out


def parse_scalars(src):
    m = re.search(r"const DATE_RANGE = \{ from: '([\d-]+)', to: '([\d-]+)' \};", src)
    if not m:
        raise SafetyError('DATE_RANGE 상수를 찾지 못했습니다.')
    return {'from': m.group(1), 'to': m.group(2)}


def extract_single_line_block(src, name, indent):
    """`{indent}const {name} = {...};` — 한 줄짜리 블록(TOTAL_DAILY)을 찾아 (start, end, body) 반환."""
    pattern = re.compile(r'^' + re.escape(indent) + r'const ' + re.escape(name) + r' = (\{.*?\});$', re.M)
    m = pattern.search(src)
    if not m:
        raise SafetyError(f'{name} 블록을 찾지 못했습니다 — HTML 구조가 바뀐 것 같습니다. 수동 확인 필요.')
    return m.start(), m.end(), m.group(1)


# ---------------------------------------------------------------------------
# 2. 신규 데이터 로드
# ---------------------------------------------------------------------------

def _read_rows(indir, fname):
    path = os.path.join(indir, fname)
    if not os.path.exists(path):
        raise SafetyError(f'{indir}에 {fname}이 없습니다.')
    with open(path, encoding='utf-8') as f:
        return json.load(f).get('rows', [])


def _read_single_value(indir, fname, field='activeUsers'):
    rows = _read_rows(indir, fname)
    if not rows:
        raise SafetyError(f'{fname}에 결과 행이 없습니다 — GA4 쿼리가 비정상일 가능성이 있습니다.')
    return rows[0][field]


def load_total_incremental(indir):
    """반환: ({date: activeUsers}, all_dates) — total_daily.json(소스 필터 없음)."""
    rows = _read_rows(indir, 'total_daily.json')
    total_daily_incr = {r['date']: (r['activeUsers'] or 0) for r in rows}
    all_dates = sorted(total_daily_incr)
    if not all_dates:
        raise SafetyError('신규 일별 데이터가 0건입니다 — GA4 쿼리가 실패했거나 범위가 잘못됐을 가능성이 있습니다.')
    return total_daily_incr, all_dates


def load_firstuser_incremental(indir):
    """반환: ({group_key: {date: [u, s]}}, all_dates, label_warnings) —
    firstuser_raw_incremental.json을 FIRST_USER_LABEL_TO_GROUP으로 단순 합산(정확함 —
    firstUserSource는 사용자당 평생 1개). 매핑에 없는 값은 classify_source()로 자동
    분류해서 그대로 합산에 포함한다(단순 합산이 정확하므로 병합 쿼리가 필요 없어
    즉시 정확하다)."""
    incr = {k: {} for k in GROUP_KEYS}
    rows = _read_rows(indir, 'firstuser_raw_incremental.json')
    unknown = sorted({r['source'] for r in rows if r['source'] not in FIRST_USER_LABEL_TO_GROUP})
    label_warnings = [
        f"신규 firstUserSource 값 '{lbl}' → {classify_source(lbl)} 자동 분류(사람 확인 권장)"
        for lbl in unknown
    ]
    for r in rows:
        gkey = FIRST_USER_LABEL_TO_GROUP.get(r['source']) or classify_source(r['source'])
        bucket = incr[gkey].setdefault(r['date'], [0, 0])
        bucket[0] += r['activeUsers'] or 0
        bucket[1] += r['sessions']

    all_dates = sorted({d for series in incr.values() for d in series})
    return incr, all_dates, label_warnings


def load_firstuser_period(indir, fname='firstuser_raw_period.json'):
    """반환: ({group_key: int}, label_warnings) — <fname>(기본 firstuser_raw_period.json)을
    그룹별로 단순 합산(정확함). 매핑에 없는 값은 classify_source()로 자동 분류해서 포함한다.
    fname을 바꿔 넣으면(예: recent7_firstuser_raw.json) 같은 로직으로 다른 기간의 period
    파일도 집계할 수 있다(최근 7일 서브합계용)."""
    totals = {k: 0 for k in GROUP_KEYS}
    rows = _read_rows(indir, fname)
    unknown = sorted({r['source'] for r in rows if r['source'] not in FIRST_USER_LABEL_TO_GROUP})
    label_warnings = [
        f"신규 firstUserSource 값 '{lbl}' → {classify_source(lbl)} 자동 분류(사람 확인 권장)"
        for lbl in unknown
    ]
    for r in rows:
        gkey = FIRST_USER_LABEL_TO_GROUP.get(r['source']) or classify_source(r['source'])
        totals[gkey] += r['activeUsers'] or 0
    return totals, label_warnings


# ---------------------------------------------------------------------------
# 3. 병합 + 윈도우 슬라이딩
# ---------------------------------------------------------------------------

def merge_and_slide(old_series, incr_series, new_from, new_to):
    """old_series: {date:[u,s]} 또는 {date:u}. incr_series의 값으로 덮어쓰기 허용(최근 며칠은
    재확정되며 값이 바뀔 수 있음 — 퍼널 리포트와 달리 이 리포트는 덮어쓰기를 막지 않는다).
    그 다음 new_from~new_to 범위 밖 날짜는 전부 제거해 윈도우를 정확히 28일로 유지한다."""
    combined = dict(old_series)
    combined.update(incr_series)
    return {d: v for d, v in combined.items() if new_from <= d <= new_to}


# ---------------------------------------------------------------------------
# 4. 검증
# ---------------------------------------------------------------------------

def validate_group_series(label, new_daily, new_totals, new_from, new_to):
    """FIRST_USER_* 그룹(GROUP_KEYS) 일별/기간 값 검증. label은 에러 메시지 접두사."""
    warnings = []

    for gkey, series in new_daily.items():
        for d, (u, s) in series.items():
            if d < new_from or d > new_to:
                raise SafetyError(f'G-WINDOW 위반: {label}.{gkey} {d}가 윈도우({new_from}~{new_to}) 밖에 남아있습니다.')
            if u < 0 or s < 0:
                raise SafetyError(f'G6 위반: {label}.{gkey} {d} 값에 음수 포함 ({u}, {s})')

    for gkey in GROUP_KEYS:
        day_vals = [v[0] for v in new_daily[gkey].values()]
        period_val = new_totals[gkey]
        if period_val < 0:
            raise SafetyError(f'G6 위반: {label}.{gkey}가 음수입니다.')
        if day_vals:
            day_sum, day_max = sum(day_vals), max(day_vals)
            if not (day_max <= period_val <= day_sum):
                warnings.append(
                    f'{label}.{gkey}: 기간 합계(dedup)={period_val}가 일별 활성사용자 범위 [{day_max}, {day_sum}] '
                    f'밖입니다 — 재조회 결과를 확인하세요(경고만, 중단하지 않음).'
                )

    return warnings


def validate_total_daily(new_total_daily, new_total_period, new_from, new_to):
    warnings = []

    for d, u in new_total_daily.items():
        if d < new_from or d > new_to:
            raise SafetyError(f'G-WINDOW 위반: TOTAL_DAILY {d}가 윈도우 밖에 남아있습니다.')
        if u < 0:
            raise SafetyError(f'G6 위반: TOTAL_DAILY {d} 값이 음수입니다 ({u})')

    if new_total_period < 0:
        raise SafetyError('G6 위반: TOTAL_PERIOD가 음수입니다.')
    total_day_vals = list(new_total_daily.values())
    if total_day_vals:
        day_sum, day_max = sum(total_day_vals), max(total_day_vals)
        if not (day_max <= new_total_period <= day_sum):
            warnings.append(
                f'TOTAL_PERIOD={new_total_period}가 일별 합 범위 [{day_max}, {day_sum}] 밖입니다 — 확인 권장.'
            )

    expected_dates = window_dates(new_from, new_to)
    if set(new_total_daily) != set(expected_dates):
        missing = sorted(set(expected_dates) - set(new_total_daily))
        extra = sorted(set(new_total_daily) - set(expected_dates))
        if missing:
            warnings.append(f'TOTAL_DAILY에 누락된 날짜: {missing} (GA4가 0으로 응답했거나 쿼리 범위 확인 필요)')
        if extra:
            raise SafetyError(f'TOTAL_DAILY에 윈도우 밖 날짜가 남아있습니다: {extra}')

    return warnings


def window_dates(new_from, new_to):
    d0 = date.fromisoformat(new_from)
    d1 = date.fromisoformat(new_to)
    return [(d0 + timedelta(days=i)).isoformat() for i in range((d1 - d0).days + 1)]


# ---------------------------------------------------------------------------
# 5. 재직렬화
# ---------------------------------------------------------------------------

def render_daily_block(name, data):
    lines = [f'  const {name} = {{']
    for key in GROUP_KEYS:
        json_str = json.dumps(dict(sorted(data[key].items())), separators=(',', ':'))
        lines.append(f'    {key}: {json_str},')
    lines.append('  };')
    return '\n'.join(lines)


def render_totals_block(name, totals):
    lines = [f'  const {name} = {{']
    for key in GROUP_KEYS:
        lines.append(f'    {key}: {totals[key]},')
    lines.append('  };')
    return '\n'.join(lines)


def render_total_daily(total_daily):
    json_str = json.dumps(dict(sorted(total_daily.items())), separators=(',', ':'))
    return f'  const TOTAL_DAILY = {json_str};'


def render_recent7_totals(totals):
    parts = ', '.join(f'{k}: {totals[k]}' for k in GROUP_KEYS)
    return f'  const RECENT7_FIRST_USER_TOTALS = {{ {parts} }};'


def patch_scalars(src, new_from, new_to, total_period, generated_at):
    src = re.sub(
        r"const DATE_RANGE = \{ from: '[\d-]+', to: '[\d-]+' \};",
        f"const DATE_RANGE = {{ from: '{new_from}', to: '{new_to}' }};",
        src,
    )
    src = re.sub(r'const TOTAL_PERIOD = \d+;', f'const TOTAL_PERIOD = {total_period};', src)
    src = re.sub(r"const GENERATED_AT = '.*?';", f"const GENERATED_AT = '{generated_at}';", src)
    return src


def patch_recent7_scalars(src, recent7_from, recent7_to, recent7_total):
    src, n1 = re.subn(
        r"const RECENT7_RANGE = \{ from: '[\d-]+', to: '[\d-]+' \};",
        f"const RECENT7_RANGE = {{ from: '{recent7_from}', to: '{recent7_to}' }};",
        src,
    )
    if n1 != 1:
        raise SafetyError('RECENT7_RANGE 블록을 찾지 못했습니다 — HTML 구조가 바뀐 것 같습니다. 수동 확인 필요.')
    src, n2 = re.subn(r'const RECENT7_TOTAL = \d+;', f'const RECENT7_TOTAL = {recent7_total};', src)
    if n2 != 1:
        raise SafetyError('RECENT7_TOTAL 블록을 찾지 못했습니다 — HTML 구조가 바뀐 것 같습니다. 수동 확인 필요.')
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

    _, _, total_daily_body = extract_single_line_block(src, 'TOTAL_DAILY', '  ')
    _, _, fu_daily_body = extract_block(src, 'FIRST_USER_DAILY', '  ')

    old_fu_daily = parse_daily_block(fu_daily_body)
    for k in GROUP_KEYS:
        old_fu_daily.setdefault(k, {})
    old_total_daily = json.loads(total_daily_body.strip())

    incr_total_daily, incoming_dates = load_total_incremental(args.indir)
    incr_fu_daily, fu_incoming_dates, fu_incr_label_warnings = load_firstuser_incremental(args.indir)

    new_to = max(incoming_dates)
    new_from_date = date.fromisoformat(new_to) - timedelta(days=WINDOW_DAYS - 1)
    new_from = new_from_date.isoformat()

    if new_to <= date_range['to'] and not incoming_dates:
        print(f'이미 최신 상태입니다(마지막 수록일 {date_range["to"]}).')
        return

    extra_warnings = []
    if not fu_incoming_dates or max(fu_incoming_dates) < new_to:
        extra_warnings.append(
            f'firstuser_raw_incremental.json에 {new_to}까지의 데이터가 없습니다 — '
            f'FIRST_USER_DAILY가 TOTAL_DAILY보다 최신성이 뒤처질 수 있습니다.'
        )

    new_total_daily = merge_and_slide({}, dict(old_total_daily, **incr_total_daily), new_from, new_to)
    new_fu_daily = {k: merge_and_slide(old_fu_daily.get(k, {}), incr_fu_daily.get(k, {}), new_from, new_to) for k in GROUP_KEYS}

    new_fu_totals, fu_period_label_warnings = load_firstuser_period(args.indir)
    new_total_period = _read_single_value(args.indir, 'total_period.json')

    # --- 최근 7일 서브합계(RECENT7_*) — 새 윈도우의 가장 최근 7일, 항상 new_to 기준 ---
    recent7_to = new_to
    recent7_from = (date.fromisoformat(new_to) - timedelta(days=6)).isoformat()
    new_recent7_total = _read_single_value(args.indir, 'recent7_total.json')
    new_recent7_fu_totals, recent7_label_warnings = load_firstuser_period(args.indir, 'recent7_firstuser_raw.json')
    if new_recent7_total < 0:
        raise SafetyError(f'RECENT7_TOTAL이 음수입니다: {new_recent7_total}')
    if new_recent7_total > new_total_period:
        raise SafetyError(
            f'RECENT7_TOTAL({new_recent7_total})이 TOTAL_PERIOD({new_total_period})보다 큽니다 — '
            f'최근 7일은 28일 전체의 부분집합이라 있을 수 없는 값입니다. 쿼리 기간을 재확인하세요.'
        )

    warnings = extra_warnings
    warnings += fu_incr_label_warnings + fu_period_label_warnings + recent7_label_warnings
    warnings += validate_total_daily(new_total_daily, new_total_period, new_from, new_to)
    warnings += validate_group_series('FIRST_USER', new_fu_daily, new_fu_totals, new_from, new_to)

    generated_at = args.generated_at or datetime.now(timezone.utc).strftime(GENERATED_AT_FMT)

    new_src = src
    td_start, td_end, _ = extract_single_line_block(new_src, 'TOTAL_DAILY', '  ')
    new_src = replace_block_text(new_src, td_start, td_end, render_total_daily(new_total_daily))

    fud_start, fud_end, _ = extract_block(new_src, 'FIRST_USER_DAILY', '  ')
    new_src = replace_block_text(new_src, fud_start, fud_end, render_daily_block('FIRST_USER_DAILY', new_fu_daily))

    fut_start, fut_end, _ = extract_block(new_src, 'FIRST_USER_TOTALS', '  ')
    new_src = replace_block_text(new_src, fut_start, fut_end, render_totals_block('FIRST_USER_TOTALS', new_fu_totals))

    new_src = patch_scalars(new_src, new_from, new_to, new_total_period, generated_at)

    r7t_start, r7t_end, _ = extract_single_line_block(new_src, 'RECENT7_FIRST_USER_TOTALS', '  ')
    new_src = replace_block_text(new_src, r7t_start, r7t_end, render_recent7_totals(new_recent7_fu_totals))
    new_src = patch_recent7_scalars(new_src, recent7_from, recent7_to, new_recent7_total)

    # --- 스모크 테스트: 재작성한 소스를 다시 파싱해 라운드트립 일치 확인 ---
    _, _, chk_total_daily_body = extract_single_line_block(new_src, 'TOTAL_DAILY', '  ')
    _, _, chk_fu_daily_body = extract_block(new_src, 'FIRST_USER_DAILY', '  ')
    assert json.loads(chk_total_daily_body.strip()) == new_total_daily
    assert parse_daily_block(chk_fu_daily_body) == new_fu_daily
    chk_range = parse_scalars(new_src)
    assert chk_range == {'from': new_from, 'to': new_to}
    m_r7r = re.search(r"const RECENT7_RANGE = \{ from: '([\d-]+)', to: '([\d-]+)' \};", new_src)
    assert m_r7r and m_r7r.group(1) == recent7_from and m_r7r.group(2) == recent7_to
    assert re.search(rf'const RECENT7_TOTAL = {new_recent7_total};', new_src)

    seen_warnings = set()
    warnings = [w for w in warnings if not (w in seen_warnings or seen_warnings.add(w))]

    print('=== update_ga4_channel_unsedang.py 요약 ===')
    print(f'윈도우: {date_range["from"]}~{date_range["to"]} -> {new_from}~{new_to} (28일 유지, 롤링)')
    print(f'[첫 사용자 소스] 그룹별 기간 합계(활성사용자): {new_fu_totals}')
    print(f'전체 기간 합계(활성사용자): {new_total_period}')
    print(f'최근 7일 서브합계 {recent7_from}~{recent7_to}: 전체 {new_recent7_total}, 그룹별 {new_recent7_fu_totals}')
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
    fd, tmp_path = tempfile.mkstemp(dir=dir_, prefix='.ga4-channel-', suffix='.tmp')
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
