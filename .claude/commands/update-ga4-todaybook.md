---
description: 오늘의 지식 리포트(html/db-data-todaybook.html)의 "GA4 활성 현황" 섹션을 매일 갱신한다. 서비스 오픈일(2026-10-13) 고정 시작점부터 D-1까지 누적되는 구조이며, 새 날짜만 추가한다(윈도우 롤링 아님).
argument-hint: "[--dry-run]"
---

# 오늘의 지식 GA4 활성 현황 누적 업데이트

인자: `$ARGUMENTS`

## §0 목적과 범위 (반드시 읽을 것)

`html/db-data-todaybook.html`의 `<div id="ga4Summary">` 카드는 GA4 `todaybook` 계정
(Supermetrics `ds_id='GAWA'`, `ds_accounts='556152838'`) 데이터로 서비스 오픈일
**2026-10-13 고정 시작점**부터 D-1까지 **누적**되는 일별 상세를 보여준다
(`html/ga4-ainote-kpi-unsedang.html`과 같은 철학 — 롤링 윈도우 아님, 기존 날짜는 절대
불변, 새 날짜만 추가). 이 리포트는 **BigQuery가 아니라 Supermetrics를 쓴다** —
todaybook GA4 속성(556152838)은 BigQuery export가 연동돼 있지 않다
(`docs/bigquery-ga4-mapping.md`의 운세당 전환과는 무관).

**공통 필터**: `hostName == 'web.todaybook.kr'` — dev/api/localhost 등 테스트 호스트를
제외해야 한다(실측 확인됨, `docs/todaybook-data.md` "Supermetrics 실측 확인" 절 참고).

**9개 지표 중 3개(`dauPaid`, `ebookUsers`, `audiobookUsers`)는 현재 조회 불가**다.
Supermetrics GAWA 커넥터가 GA4 맞춤 측정기준(`customUser:member_status`,
`customEvent:format`)을 노출하지 않기 때문이다(`contentType`은 예외 — GA4 표준
디멘션으로 노출되어 조회 가능, 지식카드/북노트 구분에 이미 쓰고 있음). 이 3개는 항상
`null`로 채운다 — **추측값을 넣지 않는다.** 해소 경로는 `docs/todaybook-data.md`
"Supermetrics 실측 확인" 절 참고(GA4 Audience 생성 또는 GTM 이벤트명 분리).

**`mauToDate`(월 누적 MAU)는 요청서 원문(월초~해당일)이 아니라 `max(그 달 1일,
2026-10-13)`~해당일로 클램프한다.** 오픈일 이전(10/1~10/12)에도 QA/사전 트래픽이
GA4에 잡혀 있어(실측 확인, 일별 2~13명) 원문대로 하면 10/13 MAU가 같은 날 DAU보다
커지는 역전이 생긴다 — 사용자 확인(2026-10-15)으로 클램프 방식을 채택했다.

**이 리포트는 비집계 지표(activeUsers/totalUsers)의 날짜 간 합계를 만들지 않는다**
(요청서가 "더하면 안 된다"고 명시). 그래서 마인드케어의 "단순 합산 + 한계 명시" 타협도,
AI노트의 "기간 합계 재조회"도 쓰지 않는다 — **기간 합계 쿼리 자체가 없다.**

DB 섹션(가입자 현황, `api.todaybook.kr`)은 브라우저가 페이지 로드 시 직접 fetch하는
실시간 영역이라 이 커맨드가 건드리지 않는다.

이 커맨드가 실제로 Supermetrics를 호출하는 건 여기(에이전트)뿐이다.
`scripts/update_ga4_todaybook.py`는 HTML 패치만 담당하며 MCP를 호출하지 않는다.

## §1 사전 확인

1. `get_today` 툴로 오늘 날짜(UTC)를 확정한다. `new_to` = 어제(UTC).
2. `grep -n "const GA4_RANGE" html/db-data-todaybook.html`로 기존 `to`를 읽는다.
   `new_to`가 기존 `to`보다 늦지 않으면 "이미 최신입니다"로 보고하고 **쿼리 없이 종료**한다.
3. `incr_from` = `max('2026-10-13', 기존 to − 2일)` (GA4 확정 지연 보정 — 최근 3일을
   다시 조회해 값이 바뀌어도 반영한다).
4. `manage_user_and_team(action='get_prioritised_accounts', ds_id='GAWA')`로 우선 계정
   3개에 `556152838`이 포함돼 있는지 확인한다. **빠져 있으면 중단**하고(쿼터 소모 방지)
   사용자에게 보고한다 — 추측으로 `set_prioritised_accounts`를 다시 호출하지 않는다.

## §2 GA4 쿼리 (ds_id='GAWA', ds_accounts='556152838')

`date_range_type='custom'`, `start_date=incr_from`, `end_date=new_to`,
`filters="hostName == 'web.todaybook.kr'"` (+ 지표별 추가 필터)로 아래를 조회한다.
모두 `fields`에 `date`를 포함해 일별 행으로 받는다.

| 지표(JSON 키) | fields | 추가 필터 |
|---|---|---|
| `dau` | `date,activeUsers` | (공통 필터만) |
| `cardReadUsers` | `date,contentType,totalUsers` | `eventName == 'content_read_complete' AND contentType == 'knowledge_card'` |
| `booknoteReadUsers` | `date,contentType,totalUsers` | `eventName == 'content_read_complete' AND contentType == 'booknote'` |
| `bookchatUsers` | `date,totalUsers` | `eventName == 'bookchat_start'` |
| `bookUsers` | `date,totalUsers` | `eventName == 'book_open'` |

`dauPaid`/`ebookUsers`/`audiobookUsers`는 조회하지 않는다(§0) — 항상 `null`.

**주의**:
- 연산자 양쪽에 공백 필수(`docs/ga4_guide.md` §2-1). `contentType`은 필터뿐 아니라
  **`fields`에도 반드시 포함**해야 한다(디멘션 미포함 시 필터가 무시되는 함정 — §2-2).
- **0건인 날짜는 행 자체가 생략되어 돌아온다** — 빠진 날짜는 `0`으로 채워서 `incr_from
  ~new_to` 구간을 모두 채운다(`dau`는 서비스가 살아있는 한 0이 나오면 이상 신호이므로
  별도 확인).
- 응답이 비동기(`schedule_id`)면 `get_async_query_results`로 완료까지 폴링한다.

### §2-1 `mauToDate` 전용 (날짜별 개별 쿼리 — §0의 클램프 적용)

`incr_from~new_to`의 **각 날짜마다** 1건씩, `fields=activeUsers`(date 디멘션 없음),
`filters="hostName == 'web.todaybook.kr'"`:
- `start_date = max(그 날짜가 속한 달의 1일, '2026-10-13')`
- `end_date = 그 날짜`

예: 10-14는 `start_date='2026-10-13'`(1일이 아니라 오픈일로 클램프), `end_date='2026-10-14'`.
월이 바뀌면(예: 11월) `start_date`가 그 달 1일로 정상 복귀한다(이미 오픈일보다 늦으므로
클램프가 자연히 해제됨).

## §3 임시 JSON 저장

스크래치패드 아래 `data.json` 하나를 Write (경로는 `/tmp` 직하가 아니라 세션
스크래치패드 디렉터리 사용):

```json
{
  "range": {"from": "YYYY-MM-DD", "to": "YYYY-MM-DD"},
  "daily": [
    {"date": "YYYY-MM-DD", "dau": N, "dauPaid": null, "mauToDate": N,
     "cardReadUsers": N, "booknoteReadUsers": N, "bookchatUsers": N,
     "bookUsers": N, "ebookUsers": null, "audiobookUsers": null}
    // incr_from~new_to 사이 날짜순(오름차순), 공백 없이 전부
  ]
}
```

`range.from`은 `incr_from`, `range.to`는 `new_to`. 지표가 나중에 열리면(§0 해소 경로)
해당 키에 `null` 대신 실제 값을 넣으면 된다 — 스크립트가 자동으로 반영한다.

## §4 스크립트 실행

먼저 진단만:
```
python3 scripts/update_ga4_todaybook.py --html html/db-data-todaybook.html --data <경로>/data.json --dry-run
```
출력된 요약(전체 누적 범위, 변경 행 수, 경고)을 확인한 뒤 `--dry-run`을 떼고 재실행한다.

`[SafetyError]`로 중단되면 **절대 우회하지 말고** 에러 메시지를 그대로 사용자에게
보고하고 원인을 파악한다(HTML 블록을 못 찾음, 날짜가 오픈일보다 이름, 날짜 공백,
음수/비정수 값 등).

## §5 렌더 검증 — 기본 생략

기본적으로 데이터 갱신까지만 하고 브라우저 렌더 확인은 생략한다. 사용자가 명시적으로
요청할 때만 Playwright로 확인하고, `.playwright-mcp/` 산출물은 확인 직후 삭제한다.

## §6 무인 스케줄 실행 시 (routine으로 호출된 경우)

사용자 확인을 기다리지 말고 끝까지 자동으로 진행한다:
- 신규 데이터가 없으면("이미 최신입니다") 아무 파일도 건드리지 말고 그대로 종료한다.
- 신규 데이터가 있어서 `html/db-data-todaybook.html`이 갱신됐다면, `git add html/db-data-todaybook.html` /
  commit(메시지: `"오늘의 지식 GA4 활성 현황 자동 업데이트: <이전 범위> -> <새 범위>"`) /
  push까지 반드시 완료한다. 저장소는 `origin/main`에 이미 연결돼 있다. daylog는
  `.gitignore`에 등록된 로컬 전용 파일이라 git add 대상에서 뺀다(§7에서 로컬에만 작성).
- §1-4(우선 계정 미포함)로 중단되면 커밋 없이, 쿼터를 임의로 건드리지 않고 그대로 종료한다.
- `[SafetyError]`로 중단되면 우회 플래그 없이, 무엇이 왜 실패했는지 세션 결과에 명확히
  남기고 커밋 없이 종료한다.

## §7 보고 + daylog

1. 스크립트 출력 요약(전체 누적 범위, 변경 행 수, 경고)을 사용자에게 전달한다.
2. **이 커맨드는 실행할 때마다** `daylog/<오늘 날짜>.md`에 append한다:
   ```markdown
   ## <오늘 날짜> 핸드오프 — 오늘의 지식 GA4 활성 현황 업데이트
   - 한 일: /update-ga4-todaybook 실행, {incr_from}~{new_to} 추가
   - 변경 파일: html/db-data-todaybook.html
   - 다음: 특이사항 없음 (또는 스크립트 경고 내용 요약)
   ```
   파일이 없으면 `CLAUDE.md` 규약대로 머리말을 붙여 새로 만든다.
