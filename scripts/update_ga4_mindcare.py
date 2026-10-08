#!/usr/bin/env python3
"""
마인드케어 리포트(html/db-data-mindcare.html)의 GA4 활성 현황 섹션 갱신 스크립트.

이 섹션은 "최근 7일 vs 이전 7일" 두 기간의 합계만 보여주는 단순 스냅샷이다(일별 누적이나
윈도우 슬라이딩이 아니다) — 매 실행마다 두 기간을 처음부터 다시 조회해 통째로 교체한다.
activeUsers는 비집계 지표라 날짜를 밀어내고 더하는 방식 자체가 성립하지 않기 때문이다.

통신사(KT/LGU+/SKT) 구분은 GA4에서 신뢰 가능한 방법을 찾지 못해(호스트명 트래픽 비율이
가입자 규모 비율과 불일치) 넣지 않는다 — 서비스 전체 합계만 다룬다(2026-10-08 결정).

이 스크립트는 Supermetrics를 직접 호출하지 않는다(에이전트만 MCP 툴 호출 가능).
`.claude/commands/update-ga4-mindcare.md`가 미리 JSON 파일을 만들어두면 이 스크립트가
그것을 읽어 HTML에 반영한다.

사용법:
    python3 update_ga4_mindcare.py --html <path> --data <json경로> [--dry-run] [--generated-at STR] [--no-backup]

입력 JSON 스키마:
    {
      "range": {"recentFrom": "YYYY-MM-DD", "recentTo": "YYYY-MM-DD",
                 "prevFrom": "YYYY-MM-DD", "prevTo": "YYYY-MM-DD"},
      "recent": {"activeUsers": N, "breathing": N, "transcription": N, "careAudio": N},
      "prev":   {"activeUsers": N, "breathing": N, "transcription": N, "careAudio": N}
    }
"""
import argparse
import json
import os
import re
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone

METRIC_KEYS = ['activeUsers', 'breathing', 'transcription', 'careAudio']

GENERATED_AT_FMT = '%Y-%m-%d %H:%M UTC (Supermetrics GA4/GAWA 조회, 정적 스냅샷)'


class SafetyError(Exception):
    """검증 실패 — 원본 파일은 절대 건드리지 않고 여기서 중단."""


def load_data(path):
    if not os.path.exists(path):
        raise SafetyError(f'{path}가 없습니다.')
    with open(path, encoding='utf-8') as f:
        d = json.load(f)
    for section in ('range', 'recent', 'prev'):
        if section not in d:
            raise SafetyError(f'입력 JSON에 "{section}" 섹션이 없습니다.')
    for k in ('recentFrom', 'recentTo', 'prevFrom', 'prevTo'):
        if k not in d['range']:
            raise SafetyError(f'range에 "{k}"가 없습니다.')
    for section in ('recent', 'prev'):
        for k in METRIC_KEYS:
            if k not in d[section]:
                raise SafetyError(f'{section}에 지표 "{k}"가 없습니다.')
            if not isinstance(d[section][k], int) or d[section][k] < 0:
                raise SafetyError(f'{section}.{k} 값이 올바르지 않습니다(음수 또는 정수 아님): {d[section][k]!r}')
    return d


def validate_range(range_):
    recent_from = date.fromisoformat(range_['recentFrom'])
    recent_to = date.fromisoformat(range_['recentTo'])
    prev_from = date.fromisoformat(range_['prevFrom'])
    prev_to = date.fromisoformat(range_['prevTo'])

    if (recent_to - recent_from).days != 6:
        raise SafetyError(f'recentFrom~recentTo가 7일 범위가 아닙니다: {range_["recentFrom"]}~{range_["recentTo"]}')
    if (prev_to - prev_from).days != 6:
        raise SafetyError(f'prevFrom~prevTo가 7일 범위가 아닙니다: {range_["prevFrom"]}~{range_["prevTo"]}')
    if prev_to >= recent_from:
        raise SafetyError(f'이전 7일({range_["prevTo"]})이 최근 7일 시작({range_["recentFrom"]})보다 앞서지 않습니다.')
    if (recent_from - prev_to).days != 1:
        raise SafetyError(
            f'이전 7일과 최근 7일 사이에 공백/중복이 있습니다: prevTo={range_["prevTo"]}, recentFrom={range_["recentFrom"]}'
        )


def patch_html(src, data, generated_at):
    new_range_line = (
        "  const GA4_RANGE = {{ recentFrom: '{recentFrom}', recentTo: '{recentTo}', "
        "prevFrom: '{prevFrom}', prevTo: '{prevTo}' }};"
    ).format(**data['range'])

    def render_totals(period_key):
        vals = data[period_key]
        parts = ', '.join(f'{k}: {vals[k]}' for k in METRIC_KEYS)
        return f'    {period_key}: {{ {parts} }},'

    new_totals_block = (
        '  const GA4_TOTALS = {\n'
        + render_totals('recent') + '\n'
        + render_totals('prev') + '\n'
        + '  };'
    )

    src, n1 = re.subn(r"^  const GA4_RANGE = \{.*?\};$", new_range_line, src, count=1, flags=re.M)
    if n1 != 1:
        raise SafetyError('GA4_RANGE 블록을 찾지 못했습니다 — HTML 구조가 바뀐 것 같습니다. 수동 확인 필요.')

    src, n2 = re.subn(
        r"^  const GA4_TOTALS = \{\n.*?\n  \};$",
        new_totals_block,
        src,
        count=1,
        flags=re.M | re.S,
    )
    if n2 != 1:
        raise SafetyError('GA4_TOTALS 블록을 찾지 못했습니다 — HTML 구조가 바뀐 것 같습니다. 수동 확인 필요.')

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
    validate_range(data['range'])

    warnings = []
    for section in ('recent', 'prev'):
        if data[section]['breathing'] > data[section]['activeUsers']:
            warnings.append(f'{section}.breathing({data[section]["breathing"]})가 {section}.activeUsers({data[section]["activeUsers"]})보다 큽니다 — 확인 권장.')
        if all(data[section][k] == 0 for k in METRIC_KEYS):
            warnings.append(f'{section} 전체 지표가 0입니다 — GA4 쿼리가 비정상일 가능성이 있습니다.')

    generated_at = args.generated_at or datetime.now(timezone.utc).strftime(GENERATED_AT_FMT)
    new_src = patch_html(src, data, generated_at)

    print('=== update_ga4_mindcare.py 요약 ===')
    print(f"최근 7일 {data['range']['recentFrom']}~{data['range']['recentTo']}: {data['recent']}")
    print(f"이전 7일 {data['range']['prevFrom']}~{data['range']['prevTo']}: {data['prev']}")
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
