#!/usr/bin/env python3
"""
오늘의 지식(todaybook) 리포트(html/db-data-todaybook.html)의 GA4 활성 현황 섹션 갱신 스크립트.

`html/ga4-ainote-kpi-unsedang.html`과 같은 철학 — **누적 성장형**(기존 날짜 절대 불변, 새
날짜만 추가)이다. `html/db-data-mindcare.html`(최근 21일 통째 교체)과는 다르다. 서비스
오픈일 2026-10-13이 고정 시작점이고, 매 실행마다 D-1까지 날짜가 늘어난다.

요청서(docs/todaybook-data.md)가 "사용자 수(activeUsers·totalUsers)는 더하면 안 된다"고
명시하므로, 이 리포트는 마인드케어와 달리 **일별 표에 합계 행을 두지 않는다**.

이 스크립트는 Supermetrics를 직접 호출하지 않는다(에이전트만 MCP 툴 호출 가능).
`.claude/commands/update-ga4-todaybook.md`가 미리 JSON 파일을 만들어두면 이 스크립트가
그것을 읽어 HTML에 반영한다.

사용법:
    python3 update_ga4_todaybook.py --html <path> --data <json경로> [--dry-run]
                                     [--generated-at STR] [--no-backup]

입력 JSON 스키마:
    {
      "range": {"from": "YYYY-MM-DD", "to": "YYYY-MM-DD"},  // 이번에 조회한 구간(신규분만 포함 가능)
      "daily": [
        {"date": "YYYY-MM-DD", "dau": N, "dauPaid": N|null, "mauToDate": N,
         "cardReadUsers": N, "booknoteReadUsers": N, "bookchatUsers": N,
         "bookUsers": N, "ebookUsers": N|null, "audiobookUsers": N|null},
        ...  // 날짜 오름차순, "daily"는 신규/정정 날짜만 담아도 되고 전체를 담아도 됨 —
             // 기존 HTML의 GA4_DAILY에 누적 병합(merge)된다.
      ]
    }

맞춤 측정기준(customUser:member_status, customEvent:format)이 GA4에 등록되지 않아 조회할
수 없는 지표(dauPaid/ebookUsers/audiobookUsers)는 null로 넣는다 — 0과 구분해야 한다(0은
"조회했는데 값이 0", null은 "아직 조회할 수 없음").
"""
import argparse
import json
import os
import re
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone

OPEN_DATE = '2026-10-13'  # 서비스 오픈일 — 고정 시작점, 이 이전 날짜는 담지 않는다.

METRIC_KEYS = [
    'dau', 'dauPaid', 'mauToDate',
    'cardReadUsers', 'booknoteReadUsers', 'bookchatUsers',
    'bookUsers', 'ebookUsers', 'audiobookUsers',
]

GENERATED_AT_FMT = '%Y-%m-%d %H:%M UTC (Supermetrics GA4/GAWA todaybook 556152838 조회, 정적 스냅샷)'


class SafetyError(Exception):
    """검증 실패 — 원본 파일은 절대 건드리지 않고 여기서 중단."""


# ---------------------------------------------------------------------------
# 입력 JSON 로드/검증
# ---------------------------------------------------------------------------

def load_data(path):
    if not os.path.exists(path):
        raise SafetyError(f'{path}가 없습니다.')
    with open(path, encoding='utf-8') as f:
        d = json.load(f)
    for section in ('range', 'daily'):
        if section not in d:
            raise SafetyError(f'입력 JSON에 "{section}" 섹션이 없습니다.')
    for k in ('from', 'to'):
        if k not in d['range']:
            raise SafetyError(f'range에 "{k}"가 없습니다.')
    if not isinstance(d['daily'], list) or len(d['daily']) == 0:
        raise SafetyError('daily는 비어있지 않은 배열이어야 합니다.')

    seen_dates = set()
    for i, row in enumerate(d['daily']):
        if 'date' not in row:
            raise SafetyError(f'daily[{i}]에 "date"가 없습니다.')
        rd = row['date']
        if rd in seen_dates:
            raise SafetyError(f'daily에 날짜 중복: {rd}')
        seen_dates.add(rd)
        if rd < OPEN_DATE:
            raise SafetyError(f'daily[{i}].date({rd})가 서비스 오픈일({OPEN_DATE})보다 이릅니다.')
        for k in METRIC_KEYS:
            if k not in row:
                raise SafetyError(f'daily[{i}]({rd})에 지표 "{k}"가 없습니다(없으면 null로 명시).')
            v = row[k]
            if v is not None and (not isinstance(v, int) or isinstance(v, bool) or v < 0):
                raise SafetyError(f'daily[{i}].{k} 값이 올바르지 않습니다(null 또는 음이 아닌 정수여야 함): {v!r}')
    return d


# ---------------------------------------------------------------------------
# 기존 HTML에서 GA4_DAILY 파싱 (누적 병합용)
# ---------------------------------------------------------------------------

_ROW_RE = re.compile(r'\{([^}]*)\}')
_FIELD_RE = re.compile(r"(\w+)\s*:\s*('(?:[^']*)'|null|-?\d+)")


def _parse_js_value(raw):
    if raw == 'null':
        return None
    if raw.startswith("'"):
        return raw[1:-1]
    return int(raw)


def parse_existing_daily(src):
    block = extract_block(src, 'GA4_DAILY', multi=True)
    rows = []
    for m in _ROW_RE.finditer(block):
        fields = dict(_FIELD_RE.findall(m.group(1)))
        if 'date' not in fields:
            continue
        row = {k: _parse_js_value(v) for k, v in fields.items()}
        rows.append(row)
    return {row['date']: row for row in rows}


def extract_block(src, name, multi=False):
    if multi:
        m = re.search(r'^  const ' + re.escape(name) + r' = \[\n(.*?)\n  \];$', src, re.M | re.S)
    else:
        m = re.search(r'^  const ' + re.escape(name) + r' = (\{.*?\});$', src, re.M)
    if not m:
        raise SafetyError(f'{name} 블록을 찾지 못했습니다 — HTML 구조가 바뀐 것 같습니다. 수동 확인 필요.')
    return m.group(1)


# ---------------------------------------------------------------------------
# 병합/검증
# ---------------------------------------------------------------------------

def merge_daily(old_map, incoming_rows):
    merged = dict(old_map)
    for row in incoming_rows:
        merged[row['date']] = {k: row[k] for k in METRIC_KEYS}
    return merged


def window_dates(d_from, d_to):
    out = []
    cur = date.fromisoformat(d_from)
    end = date.fromisoformat(d_to)
    while cur <= end:
        out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out


def validate_merged(merged):
    dates = sorted(merged)
    if dates[0] != OPEN_DATE:
        raise SafetyError(f'병합된 GA4_DAILY의 첫 날짜가 오픈일({OPEN_DATE})이 아닙니다: {dates[0]}')
    expected = window_dates(dates[0], dates[-1])
    missing = [d for d in expected if d not in merged]
    if missing:
        raise SafetyError(f'GA4_DAILY에 빈 날짜가 있습니다(연속이어야 함): {missing}')
    return dates


def collect_warnings(incoming_rows):
    warnings = []
    all_zero_or_null = True
    for row in incoming_rows:
        d = row['date']
        book = row.get('bookUsers')
        ebook = row.get('ebookUsers')
        audio = row.get('audiobookUsers')
        if book is not None and ebook is not None and audio is not None and (ebook + audio) > book:
            warnings.append(f'{d}: ebookUsers+audiobookUsers({ebook + audio})가 bookUsers({book})보다 큽니다 — 확인 권장.')
        dau = row.get('dau')
        dau_paid = row.get('dauPaid')
        if dau is not None and dau_paid is not None and dau_paid > dau:
            warnings.append(f'{d}: dauPaid({dau_paid})가 dau({dau})보다 큽니다 — 확인 권장.')
        if any(row.get(k) not in (0, None) for k in METRIC_KEYS):
            all_zero_or_null = False
    if all_zero_or_null:
        warnings.append('이번에 들어온 daily 전체 지표가 0 또는 null입니다 — GA4 쿼리가 비정상일 가능성이 있습니다.')
    return warnings


# ---------------------------------------------------------------------------
# 재직렬화/패치
# ---------------------------------------------------------------------------

def _render_value(v):
    return 'null' if v is None else str(v)


def render_daily(merged):
    lines = ['  const GA4_DAILY = [']
    for d in sorted(merged):
        row = merged[d]
        parts = ', '.join(f'{k}: {_render_value(row[k])}' for k in METRIC_KEYS)
        lines.append(f"    {{ date: '{d}', {parts} }},")
    lines.append('  ];')
    return '\n'.join(lines)


def patch_html(src, merged, range_from, range_to, generated_at):
    new_range_line = f"  const GA4_RANGE = {{ from: '{range_from}', to: '{range_to}' }};"
    new_daily_block = render_daily(merged)

    src, n1 = re.subn(r"^  const GA4_RANGE = \{.*?\};$", new_range_line, src, count=1, flags=re.M)
    if n1 != 1:
        raise SafetyError('GA4_RANGE 블록을 찾지 못했습니다 — HTML 구조가 바뀐 것 같습니다. 수동 확인 필요.')

    # 주의: 일반적인 lazy .*? + DOTALL은 GA4_DAILY가 빈 배열(최초 플레이스홀더)일 때 다음
    # 배열 리터럴의 닫는 "  ];"까지 통째로 집어삼키는 사고가 난다(실제로 한 번 겪었음 — 그
    # 사이에 있던 헬퍼 함수들이 전부 삭제됨). 그래서 각 행이 "    { ... }," 형태의 한 줄이라는
    # 걸 strict하게 강제해 배열 경계 밖으로 절대 못 넘어가게 한다(re.S 미사용 — 줄 단위로만 매칭).
    src, n2 = re.subn(r"^  const GA4_DAILY = \[\n(?:    \{[^\n]*\},\n)*  \];$", new_daily_block, src, count=1, flags=re.M)
    if n2 != 1:
        raise SafetyError('GA4_DAILY 블록을 찾지 못했습니다 — HTML 구조가 바뀐 것 같습니다. 수동 확인 필요.')

    src, n3 = re.subn(r"^  const GA4_GENERATED_AT = '.*?';$", f"  const GA4_GENERATED_AT = '{generated_at}';", src, count=1, flags=re.M)
    if n3 != 1:
        raise SafetyError('GA4_GENERATED_AT 블록을 찾지 못했습니다 — HTML 구조가 바뀐 것 같습니다. 수동 확인 필요.')

    return src


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--html', required=True)
    ap.add_argument('--data', required=True)
    ap.add_argument('--generated-at', default=None)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--no-backup', action='store_true')
    args = ap.parse_args()

    with open(args.html, encoding='utf-8') as f:
        src = f.read()

    data = load_data(args.data)
    old_map = parse_existing_daily(src)
    merged = merge_daily(old_map, data['daily'])
    dates = validate_merged(merged)
    warnings = collect_warnings(data['daily'])

    new_incoming = [d for d in data['daily'] if d['date'] not in old_map or old_map[d['date']] != {k: d[k] for k in METRIC_KEYS}]

    generated_at = args.generated_at or datetime.now(timezone.utc).strftime(GENERATED_AT_FMT)
    new_src = patch_html(src, merged, dates[0], dates[-1], generated_at)

    print('=== update_ga4_todaybook.py 요약 ===')
    print(f'전체 누적 범위: {dates[0]}~{dates[-1]} ({len(dates)}일), 이번 입력 {len(data["daily"])}행 중 변경 {len(new_incoming)}행')
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
    fd, tmp_path = tempfile.mkstemp(dir=dir_, prefix='.ga4-todaybook-', suffix='.tmp')
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
