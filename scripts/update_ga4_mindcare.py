#!/usr/bin/env python3
"""
마인드케어 리포트(html/db-data-mindcare.html)의 GA4 활성 현황 섹션 갱신 스크립트.

이 섹션은 "최근 21일" 일별 상세(21행)를 보여준다. 화면에서 시작일/종료일을 고르면
해당 구간의 "선택 기간 합계"를 일별 값을 단순 합산해 클라이언트에서 계산한다(별도
비집계 합계 쿼리는 넣지 않기로 사용자가 결정, 2026-10-14 — activeUsers는 비집계 지표라
동일 사용자가 여러 날 중복 집계될 수 있어 실제 순사용자 수보다 클 수 있다는 한계가 있음).

통신사(KT/LGU+/SKT) 구분은 GA4에서 신뢰 가능한 방법을 찾지 못해(호스트명 트래픽 비율이
가입자 규모 비율과 불일치) 넣지 않는다 — 서비스 전체 합계만 다룬다(2026-10-08 결정).

이 스크립트는 Supermetrics를 직접 호출하지 않는다(에이전트만 MCP 툴 호출 가능).
`.claude/commands/update-ga4-mindcare.md`가 미리 JSON 파일을 만들어두면 이 스크립트가
그것을 읽어 HTML에 반영한다.

사용법:
    python3 update_ga4_mindcare.py --html <path> --data <json경로> [--dry-run] [--generated-at STR] [--no-backup]

입력 JSON 스키마:
    {
      "range": {"from": "YYYY-MM-DD", "to": "YYYY-MM-DD"},   // 21일, from~to 포함
      "daily": [
        {"date": "YYYY-MM-DD", "activeUsers": N, "breathing": N, "transcription": N, "careAudio": N, "mtmTextInput": N},
        ...  // from~to 사이 21일, 날짜순(오름차순), 공백 없이
      ]
    }
"""
import argparse
import json
import os
import re
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone

METRIC_KEYS = ['activeUsers', 'breathing', 'transcription', 'careAudio', 'mtmTextInput']
DAY_COUNT = 21

GENERATED_AT_FMT = '%Y-%m-%d %H:%M UTC (Supermetrics GA4/GAWA 조회, 정적 스냅샷)'


class SafetyError(Exception):
    """검증 실패 — 원본 파일은 절대 건드리지 않고 여기서 중단."""


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
    if not isinstance(d['daily'], list):
        raise SafetyError('daily는 배열이어야 합니다.')
    for i, row in enumerate(d['daily']):
        if 'date' not in row:
            raise SafetyError(f'daily[{i}]에 "date"가 없습니다.')
        for k in METRIC_KEYS:
            if k not in row:
                raise SafetyError(f'daily[{i}]({row.get("date")})에 지표 "{k}"가 없습니다.')
            if not isinstance(row[k], int) or row[k] < 0:
                raise SafetyError(f'daily[{i}].{k} 값이 올바르지 않습니다(음수 또는 정수 아님): {row[k]!r}')
    return d


def validate_range(d):
    range_ = d['range']
    from_ = date.fromisoformat(range_['from'])
    to_ = date.fromisoformat(range_['to'])
    if (to_ - from_).days != DAY_COUNT - 1:
        raise SafetyError(f'from~to가 {DAY_COUNT}일 범위가 아닙니다: {range_["from"]}~{range_["to"]}')

    daily = d['daily']
    if len(daily) != DAY_COUNT:
        raise SafetyError(f'daily 배열이 {DAY_COUNT}행이 아닙니다 (실제 {len(daily)}행).')

    expected = from_
    for i, row in enumerate(daily):
        row_date = date.fromisoformat(row['date'])
        if row_date != expected:
            raise SafetyError(
                f'daily[{i}].date가 기대한 날짜가 아닙니다 (기대: {expected.isoformat()}, 실제: {row["date"]}) '
                '— 날짜순 오름차순, 공백/중복 없이 정렬되어야 합니다.'
            )
        expected += timedelta(days=1)


def render_daily(data):
    lines = ['  const GA4_DAILY = [']
    for row in data['daily']:
        parts = ', '.join(f'{k}: {row[k]}' for k in METRIC_KEYS)
        lines.append(f"    {{ date: '{row['date']}', {parts} }},")
    lines.append('  ];')
    return '\n'.join(lines)


def patch_html(src, data, generated_at):
    new_range_line = "  const GA4_RANGE = {{ from: '{from}', to: '{to}' }};".format(**data['range'])
    new_daily_block = render_daily(data)

    src, n1 = re.subn(r"^  const GA4_RANGE = \{.*?\};$", new_range_line, src, count=1, flags=re.M)
    if n1 != 1:
        raise SafetyError('GA4_RANGE 블록을 찾지 못했습니다 — HTML 구조가 바뀐 것 같습니다. 수동 확인 필요.')

    src, n2 = re.subn(r"^  const GA4_DAILY = \[\n.*?\n  \];$", new_daily_block, src, count=1, flags=re.M | re.S)
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
    validate_range(data)

    totals = {k: sum(row[k] for row in data['daily']) for k in METRIC_KEYS}
    warnings = []
    if totals['breathing'] > totals['activeUsers']:
        warnings.append(f'일별 합산 breathing({totals["breathing"]})이 activeUsers({totals["activeUsers"]})보다 큽니다 — 확인 권장.')
    if all(v == 0 for v in totals.values()):
        warnings.append('daily 전체 지표가 0입니다 — GA4 쿼리가 비정상일 가능성이 있습니다.')

    generated_at = args.generated_at or datetime.now(timezone.utc).strftime(GENERATED_AT_FMT)
    new_src = patch_html(src, data, generated_at)

    print('=== update_ga4_mindcare.py 요약 ===')
    print(f"기간 {data['range']['from']}~{data['range']['to']} ({DAY_COUNT}일), 일별 합산 참고값: {totals}")
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
    fd, tmp_path = tempfile.mkstemp(dir=dir_, prefix='.ga4-mindcare-', suffix='.tmp')
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
