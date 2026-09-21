#!/usr/bin/env python3
"""
운세당 GA4 퍼널 리포트(html/ga4-funnel-unsedang.html) 증분 업데이트 스크립트.

핵심 원칙: 기존에 임베드된 날짜/월은 절대 재조회·재계산하지 않는다. 신규 날짜만
DAILY_PAGES/DAILY_EVENTS에 추가하고, 비집계 지표인 PAGE_USERS/EVENT_USERS의
월별·연간 활성사용자는 입력 JSON에 실제로 들어있는 (경로/이벤트, 달) 조합만 덮어쓴다.

이 스크립트는 Supermetrics를 직접 호출하지 않는다(에이전트만 MCP 툴 호출 가능).
`.claude/commands/update-ga4-unsedang.md`가 미리 4개의 임시 JSON 파일을 만들어두면
이 스크립트가 그것을 읽어 HTML에 병합한다.

사용법:
    python3 update_ga4_unsedang.py --html <path> --indir <tmpdir> [--dry-run]
                                    [--generated-at STR] [--no-backup]
                                    [--allow-tail-overwrite]

입력 디렉터리(--indir) 안의 4개 파일 스키마:
    daily_pages.json  : {"rows": [{"date","path","activeUsers","sessions"}, ...]}
    daily_events.json : {"rows": [{"event","date","activeUsers","eventCount"}, ...]}
                         event ∈ preTel|postTel|coachMark|banner
    users_monthly.json: {"pages":  [{"yearMonth","path","activeUsers"}, ...],
                          "events": [{"yearMonth","event","activeUsers"}, ...]}
    users_yearly.json : {"pages":  [{"path","activeUsers"}, ...],
                          "events": [{"event","activeUsers"}, ...]}

    yearMonth는 '2026|09' 또는 '2026-09' 둘 다 허용(정규화함).
    존재하지 않는 (path/event, 달) 조합은 그냥 생략하면 된다 — 넣은 것만 갱신된다.
"""
import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone

# --- 알려진 키 (오타·경로 변경 조기 탐지용) ---
PAGE_PATH_TO_KEY = {
    '/view/home': 'home',
    '/view/csl': 'csl',
    '/view/csl/cslInfo': 'cslInfo',
    '/view/free': 'free',
    '/view/free/registrationStart': 'regStart',
    '/view/free/registrationForm': 'regForm',
    '/view/free/registrationEnd': 'regEnd',
    '/view/content': 'content',
    '/view/fortune/unseYear': 'unseYear',
}
PAGE_KEYS = list(PAGE_PATH_TO_KEY.values())
EVENT_KEYS = ['preTel', 'postTel', 'coachMark', 'banner']

GENERATED_AT_FMT = '%Y-%m-%d %H:%M UTC (Supermetrics GA4/GAWA 조회, 정적 스냅샷)'


class SafetyError(Exception):
    """검증 실패 — 원본 파일은 절대 건드리지 않고 여기서 중단."""


# ---------------------------------------------------------------------------
# 1. 기존 HTML 파싱
# ---------------------------------------------------------------------------

def extract_block(src, name, indent):
    """`{indent}const {name} = {{\n...\n{indent}}};` 블록을 찾아 (start, end, body) 반환.
    start/end는 src 안에서 이 블록 전체(마커 포함)의 문자 오프셋. body는 안쪽 내용(줄 단위)."""
    pattern = re.compile(
        r'^' + re.escape(indent) + r'const ' + re.escape(name) + r' = \{\n(.*?)\n'
        + re.escape(indent) + r'\};$',
        re.M | re.S,
    )
    m = pattern.search(src)
    if not m:
        raise SafetyError(f'{name} 블록을 찾지 못했습니다 — HTML 구조가 바뀐 것 같습니다. 수동 확인 필요.')
    return m.start(), m.end(), m.group(1)


def parse_daily_block(body):
    """`  key: {json},` 줄들을 파싱. 안쪽 {json}은 순수 JSON이라 그대로 loads."""
    out = {}
    line_re = re.compile(r'^  (\w+): (\{.*\}),$')
    for line in body.split('\n'):
        m = line_re.match(line)
        if not m:
            raise SafetyError(f'DAILY 블록의 줄을 파싱하지 못했습니다: {line[:80]}...')
        key, json_str = m.group(1), m.group(2)
        out[key] = json.loads(json_str)
    return out


USERS_LINE_RE = re.compile(
    r"^    (\w+):\s+\{ monthly: (\{.*?\}), yearly: (\d+)(?:, startDate: '([\d-]+)')? \},$"
)


def parse_users_block(body):
    """`    key:  { monthly: {...}, yearly: N[, startDate: 'D'] },` 줄들을 파싱."""
    out = {}
    for line in body.split('\n'):
        m = USERS_LINE_RE.match(line)
        if not m:
            raise SafetyError(f'USERS 블록의 줄을 파싱하지 못했습니다: {line[:80]}...')
        key, monthly_str, yearly_str, start_date = m.groups()
        monthly = json.loads(monthly_str.replace("'", '"'))
        out[key] = {'monthly': monthly, 'yearly': int(yearly_str), 'startDate': start_date}
    return out


def parse_scalars(src):
    m = re.search(r"const DATE_RANGE = \{ from: '([\d-]+)', to: '([\d-]+)' \};", src)
    if not m:
        raise SafetyError('DATE_RANGE 상수를 찾지 못했습니다.')
    date_from, date_to = m.groups()

    m = re.search(r"const MONTHS = \[(.*?)\];", src)
    if not m:
        raise SafetyError('MONTHS 상수를 찾지 못했습니다.')
    months = re.findall(r"'([\d-]+)'", m.group(1))

    return {'from': date_from, 'to': date_to}, months


# ---------------------------------------------------------------------------
# 2. 신규 데이터 로드 (에이전트가 --indir에 써둔 임시 JSON)
# ---------------------------------------------------------------------------

def _norm_ym(ym):
    """'2026|09' 또는 '2026-09' -> '2026-09'"""
    return ym.replace('|', '-')


def load_new_daily(indir):
    """범위 유효성(기존 날짜와 안 겹치는지)은 여기서 검사하지 않는다 — merge_daily()가
    키 단위로 더 정확하게 검사한다. 여기서는 형식/오타만 잡는다."""
    pages_path = os.path.join(indir, 'daily_pages.json')
    events_path = os.path.join(indir, 'daily_events.json')
    if not os.path.exists(pages_path) or not os.path.exists(events_path):
        raise SafetyError(f'{indir}에 daily_pages.json / daily_events.json이 없습니다.')

    with open(pages_path, encoding='utf-8') as f:
        pages_raw = json.load(f)
    with open(events_path, encoding='utf-8') as f:
        events_raw = json.load(f)

    new_pages = {k: {} for k in PAGE_KEYS}
    for row in pages_raw.get('rows', []):
        path, date = row['path'], row['date']
        key = PAGE_PATH_TO_KEY.get(path)
        if key is None:
            raise SafetyError(f'알 수 없는 페이지 경로: {path!r} — 오타이거나 리포트에 없던 신규 경로입니다.')
        new_pages[key][date] = [row['activeUsers'], row['sessions']]

    new_events = {k: {} for k in EVENT_KEYS}
    for row in events_raw.get('rows', []):
        event, date = row['event'], row['date']
        if event not in EVENT_KEYS:
            raise SafetyError(f'알 수 없는 이벤트 키: {event!r} (허용: {EVENT_KEYS})')
        new_events[event][date] = [row['activeUsers'], row['eventCount']]

    total_rows = sum(len(v) for v in new_pages.values()) + sum(len(v) for v in new_events.values())
    if total_rows == 0:
        raise SafetyError('신규 일별 데이터가 0건입니다 — GA4 쿼리가 실패했거나 범위가 잘못됐을 가능성이 있습니다.')

    return new_pages, new_events


def load_new_users(indir):
    monthly_path = os.path.join(indir, 'users_monthly.json')
    yearly_path = os.path.join(indir, 'users_yearly.json')
    if not os.path.exists(monthly_path) or not os.path.exists(yearly_path):
        raise SafetyError(f'{indir}에 users_monthly.json / users_yearly.json이 없습니다.')

    with open(monthly_path, encoding='utf-8') as f:
        monthly_raw = json.load(f)
    with open(yearly_path, encoding='utf-8') as f:
        yearly_raw = json.load(f)

    # {key: {yearMonth: activeUsers}}
    new_monthly = {k: {} for k in PAGE_KEYS + EVENT_KEYS}
    for row in monthly_raw.get('pages', []):
        key = PAGE_PATH_TO_KEY.get(row['path'])
        if key is None:
            raise SafetyError(f'users_monthly.json: 알 수 없는 페이지 경로 {row["path"]!r}')
        new_monthly[key][_norm_ym(row['yearMonth'])] = row['activeUsers']
    for row in monthly_raw.get('events', []):
        key = row['event']
        if key not in EVENT_KEYS:
            raise SafetyError(f'users_monthly.json: 알 수 없는 이벤트 키 {key!r}')
        new_monthly[key][_norm_ym(row['yearMonth'])] = row['activeUsers']

    # {key: activeUsers}
    new_yearly = {}
    for row in yearly_raw.get('pages', []):
        key = PAGE_PATH_TO_KEY.get(row['path'])
        if key is None:
            raise SafetyError(f'users_yearly.json: 알 수 없는 페이지 경로 {row["path"]!r}')
        new_yearly[key] = row['activeUsers']
    for row in yearly_raw.get('events', []):
        key = row['event']
        if key not in EVENT_KEYS:
            raise SafetyError(f'users_yearly.json: 알 수 없는 이벤트 키 {key!r}')
        new_yearly[key] = row['activeUsers']

    missing_yearly = [k for k in PAGE_KEYS + EVENT_KEYS if k not in new_yearly]
    if missing_yearly:
        raise SafetyError(f'연간 활성사용자 값이 누락된 키: {missing_yearly} — 13개 시리즈 전부 필요합니다.')

    return new_monthly, new_yearly


# ---------------------------------------------------------------------------
# 3. 병합
# ---------------------------------------------------------------------------

def merge_daily(old, new, allow_tail_overwrite):
    """old, new: {key: {date: [a,b]}}. 반환: 병합된 새 dict(날짜 오름차순 정렬)."""
    merged = {}
    for key in old:
        old_series = old[key]
        new_series = new.get(key, {})
        combined = dict(old_series)
        for date, vals in new_series.items():
            if date in old_series and not allow_tail_overwrite:
                raise SafetyError(
                    f'{key} {date}는 이미 존재합니다 — 기존 데이터 재조회/덮어쓰기는 금지입니다. '
                    f'의도적인 정정이라면 --allow-tail-overwrite를 쓰세요.'
                )
            combined[date] = vals
        if len(combined) < len(old_series):
            raise SafetyError(f'{key}: 병합 후 날짜 개수가 줄었습니다({len(old_series)} -> {len(combined)}) — 데이터 유실 의심.')
        merged[key] = dict(sorted(combined.items()))
    return merged


def merge_users(old_users, new_monthly):
    """old_users: {key: {monthly, yearly, startDate}}. new_monthly에 들어있는
    (key, yearMonth) 조합만 덮어쓴다. 그 외 달과 startDate는 절대 변경하지 않는다."""
    merged = {}
    for key, data in old_users.items():
        monthly = dict(data['monthly'])
        for ym, val in new_monthly.get(key, {}).items():
            monthly[ym] = val
        merged[key] = {
            'monthly': dict(sorted(monthly.items())),
            'yearly': data['yearly'],  # yearly는 별도로 apply_yearly()에서 갱신
            'startDate': data['startDate'],
        }
    return merged


def apply_yearly(users, new_yearly):
    for key in users:
        users[key]['yearly'] = new_yearly[key]
    return users


# ---------------------------------------------------------------------------
# 4. 검증
# ---------------------------------------------------------------------------

def validate(old_daily, merged_daily, old_users, merged_users):
    warnings = []

    # G1/G2: 기존 날짜 키 불변 + 개수 비감소
    for key, old_series in old_daily.items():
        merged_series = merged_daily[key]
        if len(merged_series) < len(old_series):
            raise SafetyError(f'G1 위반: {key} 날짜 개수 감소')
        for date, old_vals in old_series.items():
            if merged_series.get(date) != old_vals:
                raise SafetyError(f'G2 위반: {key} {date}의 기존 값이 변경됨 ({old_vals} -> {merged_series.get(date)})')

    # G3/G4: 영향받은 달의 monthly dedup 값이 [max(일별), sum(일별)] 범위 안인지
    for key in PAGE_KEYS + EVENT_KEYS:
        old_monthly = old_users[key]['monthly']
        new_monthly = merged_users[key]['monthly']
        daily = merged_daily[key]
        for ym, val in new_monthly.items():
            if old_monthly.get(ym) == val:
                continue  # 안 바뀐 달은 굳이 재검증 안 함
            day_vals = [v[0] for date, v in daily.items() if date.startswith(ym)]
            if not day_vals:
                continue  # 이 달에 대한 일별 데이터가 아예 없음(정상 — 이벤트 시작 전 등)
            day_sum, day_max = sum(day_vals), max(day_vals)
            if not (day_max <= val <= day_sum):
                raise SafetyError(
                    f'G3/G4 위반: {key} {ym} 월별 dedup={val}가 일별 활성사용자 범위'
                    f' [{day_max}, {day_sum}] 밖입니다. 재조회 결과를 다시 확인하세요.'
                )
            prev_val = old_monthly.get(ym)
            if prev_val:
                ratio_before = prev_val
                ratio_after = val
                if ratio_before and abs(ratio_after - ratio_before) / ratio_before > 0.5:
                    warnings.append(f'{key} {ym}: 월별 활성사용자가 {ratio_before} -> {ratio_after}로 50% 이상 변동')

    # G5: yearly는 [max(monthly), sum(monthly)] 범위 안
    for key in PAGE_KEYS + EVENT_KEYS:
        monthly_vals = list(merged_users[key]['monthly'].values())
        yearly_val = merged_users[key]['yearly']
        if monthly_vals and not (max(monthly_vals) <= yearly_val <= sum(monthly_vals)):
            raise SafetyError(
                f'G5 위반: {key} 연간 dedup={yearly_val}가 월별 합 범위'
                f' [{max(monthly_vals)}, {sum(monthly_vals)}] 밖입니다.'
            )

    # G6: 음수 금지
    for key, series in merged_daily.items():
        for date, (a, b) in series.items():
            if a < 0 or b < 0:
                raise SafetyError(f'G6 위반: {key} {date} 값에 음수 포함 ({a}, {b})')

    return warnings


def check_year_boundary(new_dates, date_from):
    base_year = date_from[:4]
    bad = [d for d in new_dates if d[:4] != base_year]
    if bad:
        raise SafetyError(
            f'G7 위반: 신규 날짜 중 연도 경계를 넘는 것이 있습니다({bad[:3]}...). '
            f'이 스크립트는 단일 연도({base_year}) 리포트 구조를 가정합니다 — '
            f'연도가 바뀌는 갱신은 리포트 구조(탭 라벨/연간 집계) 재설계가 먼저 필요합니다.'
        )


# ---------------------------------------------------------------------------
# 5. 재직렬화
# ---------------------------------------------------------------------------

def render_daily_block(name, data):
    lines = [f'const {name} = {{']
    for key, series in data.items():
        json_str = json.dumps(series, separators=(',', ':'))
        lines.append(f'  {key}: {json_str},')
    lines.append('};')
    return '\n'.join(lines)


def render_users_block(name, data):
    keys = list(data.keys())
    brace_col = max(len(k) for k in keys) + 2  # 콜론(1) + 공백(1)
    lines = [f'  const {name} = {{']
    for key in keys:
        d = data[key]
        monthly_str = json.dumps(d['monthly'], separators=(',', ':')).replace('"', "'")
        prefix = (key + ':').ljust(brace_col)
        extra = f", startDate: '{d['startDate']}'" if d['startDate'] else ''
        lines.append(f"    {prefix}{{ monthly: {monthly_str}, yearly: {d['yearly']}{extra} }},")
    lines.append('  };')
    return '\n'.join(lines)


def patch_scalars(src, new_to, months, generated_at):
    src = re.sub(
        r"const DATE_RANGE = \{ from: '[\d-]+', to: '[\d-]+' \};",
        lambda m: re.sub(r"to: '[\d-]+'", f"to: '{new_to}'", m.group(0)),
        src,
    )
    months_str = ','.join(f"'{m}'" for m in months)
    src = re.sub(r"const MONTHS = \[.*?\];", f"const MONTHS = [{months_str}];", src)
    src = re.sub(r"const GENERATED_AT = '.*?';", f"const GENERATED_AT = '{generated_at}';", src)
    return src


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
    ap.add_argument('--allow-tail-overwrite', action='store_true')
    args = ap.parse_args()

    with open(args.html, encoding='utf-8') as f:
        src = f.read()

    date_range, months = parse_scalars(src)

    _, _, daily_pages_body = extract_block(src, 'DAILY_PAGES', '')
    _, _, daily_events_body = extract_block(src, 'DAILY_EVENTS', '')
    _, _, page_users_body = extract_block(src, 'PAGE_USERS', '  ')
    _, _, event_users_body = extract_block(src, 'EVENT_USERS', '  ')

    old_daily_pages = parse_daily_block(daily_pages_body)
    old_daily_events = parse_daily_block(daily_events_body)
    old_page_users = parse_users_block(page_users_body)
    old_event_users = parse_users_block(event_users_body)
    old_daily = dict(old_daily_pages, **old_daily_events)
    old_users = dict(old_page_users, **old_event_users)

    new_pages, new_events = load_new_daily(args.indir)
    new_dates = sorted({d for series in {**new_pages, **new_events}.values() for d in series})
    if not new_dates:
        raise SafetyError('신규 데이터가 없습니다.')
    new_to = new_dates[-1]

    check_year_boundary(new_dates, date_range['from'])

    new_monthly, new_yearly = load_new_users(args.indir)

    merged_daily_pages = merge_daily(old_daily_pages, new_pages, args.allow_tail_overwrite)
    merged_daily_events = merge_daily(old_daily_events, new_events, args.allow_tail_overwrite)
    merged_daily = dict(merged_daily_pages, **merged_daily_events)

    merged_page_users = merge_users(old_page_users, new_monthly)
    merged_event_users = merge_users(old_event_users, new_monthly)
    apply_yearly(merged_page_users, new_yearly)
    apply_yearly(merged_event_users, new_yearly)
    merged_users = dict(merged_page_users, **merged_event_users)

    warnings = validate(old_daily, merged_daily, old_users, merged_users)

    new_date_range_to = max(date_range['to'], new_to)
    new_months = sorted(set(months) | {d[:7] for d in new_dates})

    generated_at = args.generated_at or datetime.now(timezone.utc).strftime(GENERATED_AT_FMT)

    # --- 재작성: 블록 치환은 원본 문자열에서 위치를 다시 찾아서 바꾼다 ---
    new_src = src

    def replace_block(text, name, indent, new_body_str):
        start, end, _ = extract_block(text, name, indent)
        return text[:start] + new_body_str + text[end:]

    new_src = replace_block(new_src, 'DAILY_PAGES', '', render_daily_block('DAILY_PAGES', merged_daily_pages))
    new_src = replace_block(new_src, 'DAILY_EVENTS', '', render_daily_block('DAILY_EVENTS', merged_daily_events))
    new_src = replace_block(new_src, 'PAGE_USERS', '  ', render_users_block('PAGE_USERS', merged_page_users))
    new_src = replace_block(new_src, 'EVENT_USERS', '  ', render_users_block('EVENT_USERS', merged_event_users))
    new_src = patch_scalars(new_src, new_date_range_to, new_months, generated_at)

    # --- 스모크 테스트: 재작성한 소스를 다시 파싱해 라운드트립 일치 확인 ---
    _, _, chk_pages_body = extract_block(new_src, 'DAILY_PAGES', '')
    _, _, chk_events_body = extract_block(new_src, 'DAILY_EVENTS', '')
    _, _, chk_page_users_body = extract_block(new_src, 'PAGE_USERS', '  ')
    _, _, chk_event_users_body = extract_block(new_src, 'EVENT_USERS', '  ')
    assert parse_daily_block(chk_pages_body) == merged_daily_pages
    assert parse_daily_block(chk_events_body) == merged_daily_events
    assert parse_users_block(chk_page_users_body) == merged_page_users
    assert parse_users_block(chk_event_users_body) == merged_event_users

    added_page_dates = sum(len(merged_daily_pages[k]) - len(old_daily_pages[k]) for k in old_daily_pages)
    added_event_dates = sum(len(merged_daily_events[k]) - len(old_daily_events[k]) for k in old_daily_events)
    touched_months = sorted({ym for m in new_monthly.values() for ym in m})

    print('=== update_ga4_unsedang.py 요약 ===')
    print(f'기간: {date_range["from"]} ~ {date_range["to"]} -> {date_range["from"]} ~ {new_date_range_to} (신규 {len(new_dates)}일)')
    print(f'추가된 날짜 키: DAILY_PAGES +{added_page_dates}개, DAILY_EVENTS +{added_event_dates}개')
    print(f'재조회 반영: monthly {touched_months} (13시리즈), yearly (13시리즈)')
    unaffected = sorted(set(months) - set(touched_months))
    print(f'미변경: {unaffected} monthly 전부')
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
