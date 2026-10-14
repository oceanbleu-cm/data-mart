---
description: 마인드케어 리포트(html/db-data-mindcare.html)의 "GA4 활성 현황" 섹션(최근 21일 일별 상세, 화면에서 기간 선택해 합계 확인)을 매일 갱신한다. 윈도우 슬라이딩이 아니라 21일 구간을 매번 처음부터 다시 조회해 통째로 교체하는 단순 스냅샷이다.
argument-hint: "[--dry-run]"
---

# 마인드케어 GA4 활성 현황 스냅샷 갱신

인자: `$ARGUMENTS`

## §0 목적과 범위 (반드시 읽을 것)

`html/db-data-mindcare.html`의 `<div id="ga4Summary">` 카드는 GA4 MINDCARE 계정(Supermetrics
`ds_id='GAWA'`, `ds_accounts='295084110'`) 데이터로 "최근 21일" 5개 지표(활성사용자 전체 /
숨명상 / 필사명상 / 오디오명상 / 게시판 상담)의 **일별 상세(21행)** 를 보여준다. 화면에서
시작일/종료일을 고르면 해당 구간의 "선택 기간 합계"를 **일별 값을 단순 합산**해서
클라이언트에서 계산한다(별도 비집계 합계 쿼리는 넣지 않기로 사용자가 결정, 2026-10-14 —
activeUsers는 비집계 지표라 동일 사용자가 여러 날 중복 집계될 수 있어 실제 순사용자 수보다
클 수 있다는 한계는 화면에 check-row로 명시되어 있다). **일별 누적이나 윈도우 슬라이딩이
아니다** — 매 실행마다 21일 구간을 처음부터 다시 조회해서 `GA4_RANGE`/`GA4_DAILY`/
`GA4_GENERATED_AT` 세 상수를 통째로 교체한다.

**통신사(KT/LGU+/SKT) 구분은 넣지 않는다.** 2026-10-08에 GA4에서 신뢰 가능한 구분 방법을
찾지 못해(호스트명 `kpassapp.*`/`upassapp.*` 트래픽 비율이 실제 가입자 규모 비율과 전혀
맞지 않음, UTM/경로에도 통신사 식별자 없음) 사용자가 "구분 없이 전체 합계만" 넣기로 결정한
결과다. 나중에 신뢰 가능한 구분 방법이 발견되기 전까지 이 결정을 바꾸지 않는다.

이 커맨드가 실제로 Supermetrics를 호출하는 건 여기(에이전트)뿐이다.
`scripts/update_ga4_mindcare.py`는 HTML 패치만 담당하며 MCP를 호출하지 않는다.

## §1 사전 확인

1. `get_today` 툴로 오늘 날짜(UTC)를 확정한다.
2. `to` = 어제(UTC), `from` = to - 20일. (총 21일, from~to 포함.)

## §2 GA4 쿼리 5건 (ds_id='GAWA', ds_accounts='295084110')

`date_range_type='custom'`, `start_date`=from, `end_date`=to, `fields=["date","activeUsers"]`
(date 디멘션 포함, 일별 값)로 아래 5개 지표를 각 1건씩 조회한다.

| 지표 | filters |
|---|---|
| 활성사용자(전체) | `pagePathWithoutQueryString != '/kpass/news2/' AND pagePathWithoutQueryString != '/kpass/recommend/'` |
| 숨명상 | `pagePathWithoutQueryString == '/breathing'` |
| 필사명상 | `pagePathWithoutQueryString == '/transcription01' OR pagePathWithoutQueryString == '/transcription02' OR pagePathWithoutQueryString == '/transcription03'` |
| 오디오명상 | `pagePathWithoutQueryString =@ '/careAudio'` |
| 게시판 상담 | `pagePathWithoutQueryString =@ '/mtmTextInput'` |

**주의**: `/kpass/news2/`, `/kpass/recommend/`는 백그라운드성 호출로 추정되는 페이지라
활성사용자(전체) 집계에서 반드시 제외한다(`docs/ga4_guide.md` MINDCARE 섹션 참고). 숨명상은
`/breathing`만(⚠️ `/breathmain`, `/breathlist`는 다른 페이지라 포함하지 않음). 필사명상은
`/transcription01~03`만(`/transcriptionCalender`는 제외). 게시판 상담은 실제 경로가
`/mtmTextInput`이 아니라 `/mtmTextInput/DEPRESS`, `/mtmTextInput/LOVE` 등 하위 카테고리로
쪼개져 있으므로 반드시 `=@`(contains)로 잡는다(`==`로 정확히 잡으면 항상 빈 결과가 나온다).
`[]`(in list) 연산자는 이 소스에서 빈 결과를 반환하는 버그가 있었음이 확인됐으니 `OR` +
`==` 조합으로 대체한다.

**0건인 날짜는 행 자체가 생략되어 돌아온다** (예: 게시판 상담은 활동이 없는 날이 대부분이라
21행 중 몇 행만 돌아올 수 있음) — 빠진 날짜는 0으로 채워서 21행을 모두 만들어야 한다.

응답이 비동기(`schedule_id`)면 `get_async_query_results`로 완료까지 폴링한다. 5건 전부
빈 배열로 오면 쿼리/필터 자체가 잘못됐을 가능성이 높다 — 그대로 0으로 채우지 말고 필터
문법을 재확인한다.

## §3 임시 JSON 저장

`mkdir -p /tmp/ga4-mindcare-update/<YYYYMMDD-HHMMSS>/` 후 `data.json` 하나를 Write:

```json
{
  "range": {"from": "YYYY-MM-DD", "to": "YYYY-MM-DD"},
  "daily": [
    {"date": "YYYY-MM-DD", "activeUsers": N, "breathing": N, "transcription": N, "careAudio": N, "mtmTextInput": N}
    // from~to 사이 21일, 날짜순(오름차순), 빠진 날 없이 모두 채워서 21개
  ]
}
```

## §4 스크립트 실행

먼저 진단만:
```
python3 scripts/update_ga4_mindcare.py --html html/db-data-mindcare.html --data <tmpdir>/data.json --dry-run
```
출력된 요약(일별 합산 참고값, 경고)을 확인한 뒤 `--dry-run`을 떼고 재실행한다.

`[SafetyError]`로 중단되면 **절대 우회하지 말고** 에러 메시지를 그대로 사용자에게
보고하고 원인을 파악한다(HTML 블록을 못 찾음, 기간이 21일이 아님, daily 행이 21개가
아니거나 날짜 공백/중복, 음수/비정수 값 등 실제 데이터 무결성 문제).

## §5 렌더 검증 — 기본 생략

기본적으로 데이터 갱신까지만 하고 브라우저 렌더 확인은 생략한다. 사용자가 명시적으로
요청할 때만 Playwright로 확인하고, `.playwright-mcp/` 산출물은 확인 직후 삭제한다.

## §6 무인 스케줄 실행 시 (routine으로 호출된 경우)

사용자 확인을 기다리지 말고 끝까지 자동으로 진행한다:
- `git add html/db-data-mindcare.html daylog/<오늘 날짜>.md` / commit(메시지:
  `"마인드케어 GA4 활성 현황 자동 업데이트: <21일 범위>"`) / push까지 반드시 완료한다.
  저장소는 `origin/main`에 이미 연결돼 있다.
- `[SafetyError]`로 중단되면 우회 플래그 없이, 무엇이 왜 실패했는지 세션 결과에 명확히
  남기고 커밋 없이 종료한다.

## §7 보고 + daylog

1. 스크립트 출력 요약(일별 합산 참고값, 경고)을 사용자에게 전달한다.
2. **이 커맨드는 실행할 때마다** `daylog/<오늘 날짜>.md`에 append한다:
   ```markdown
   ## <오늘 날짜> 핸드오프 — 마인드케어 GA4 활성 현황 스냅샷 업데이트
   - 한 일: /update-ga4-mindcare 실행, 최근 21일 {from}~{to} 갱신
   - 변경 파일: html/db-data-mindcare.html
   - 다음: 특이사항 없음 (또는 스크립트 경고 내용 요약)
   ```
   파일이 없으면 CLAUDE.md 규약대로 머리말을 붙여 새로 만든다.
