---
description: 운세당 AI 상담노트 화면별 KPI 리포트(html/ga4-ainote-kpi-unsedang.html)를 D-1까지 누적 갱신한다(2026-09-30 고정 시작점, 끝에서 밀어내지 않는 누적형 — 퍼널 리포트와 같은 철학).
argument-hint: "[--to YYYY-MM-DD] [--dry-run] [--skip-db]"
---

# AI 상담노트 KPI 리포트 누적 업데이트 (운세당)

인자: `$ARGUMENTS`

## §0 목적과 절대 원칙 (반드시 지킬 것)

이 커맨드는 `html/ga4-ainote-kpi-unsedang.html`을 **누적 성장형**으로 유지한다 — AI 상담노트
집계 시작일(`2026-09-30`)이 고정 시작점이고, 매 실행마다 D-1까지 날짜가 늘어난다. 기존
날짜는 절대 불변, 새 날짜만 추가한다(`html/ga4-channel-unsedang.html`처럼 오래된 날짜를
밀어내는 롤링 윈도우가 **아니다** — `html/ga4-funnel-unsedang.html`과 같은 철학).

데이터 출처가 **두 종류**다:
1. **GA4 BigQuery export**(`unsedang.analytics_488612198`, 2026-10-15에 Supermetrics MCP에서
   전환 — 검증 기록: `docs/bigquery-ga4-mapping.md`) — CALL/PRETEL/PAGES(aiNote·noteInfo)/
   SUBEVENTS(7종)/ENGAGEMENT/UTM_CLICK/RECO_CLICK(선생님 추천 버튼 클릭, 06 보조지표).
   `scripts/update_ga4_ainote_kpi_unsedang.py`는 BigQuery를
   직접 호출하지 않는다(에이전트만 BigQuery MCP 툴 호출 가능) — 이 커맨드(에이전트)가 미리
   JSON 파일로 떠서 `--indir`에 넣어두면 스크립트가 읽는다(JSON 스키마는 전환 전과 완전히
   동일). 기간 합계는 "새 날짜만 반영"이 아니라 **매번 전체 누적 기간을 재조회한 값으로
   통째로 교체**한다(activeUsers는 비집계 지표). 윈도우 시작일(2026-09-30)이 BQ export
   시작일(2026-08-27)보다 항상 뒤라 클램프는 불필요하다.
2. **운세당 DB API**(`consultation-stats/monthly`) — ALIMTALK/AINOTE_CONSULT_CNT/
   AINOTE_CONSULT_USR/AINOTE_REPEAT_USR/AINOTE_REPEAT_CNT/AINOTE_AFTER_REPEAT_CNT(전부
   선불 전용, 후불은 항상 0). 이 API는 인증
   없는 공개 CORS API라 **스크립트가 직접 호출**한다 — 이 커맨드가 따로 조회할 필요
   없다. 네트워크 문제 등으로 DB 쪽만 건너뛰어야 하면 `--skip-db`를 전달한다.

**`DAILY_AINOTE_USAGE`는 이 스크립트가 절대 건드리지 않는다** — 운영진이 직접 전달하는
수동 실집계(자동 수집 경로 없음). 새 날짜가 생겨도 값이 없으면 그냥 0으로 표시될 뿐
(보조지표, 목표 없음) 판정에 영향 없다. 새 값이 생기면 사람이 직접
`DAILY_AINOTE_USAGE` 딕셔너리에 추가해야 한다 — 이 커맨드의 책임이 아니다.

이 커맨드가 실제로 BigQuery(`execute_sql_readonly`)를 호출하는 건 여기(에이전트)뿐이다.
`scripts/update_ga4_ainote_kpi_unsedang.py`는 GA4 쪽 병합/재작성만 담당하고, DB API
쪽은 스크립트 자신이 직접 호출한다.

**⚠️ DB만 뒤처지는 상황(복구법)**: 직전 실행이 `--skip-db`로 DB 쪽을 건너뛰었는데 GA4는
이미 D-1까지 최신인 경우, §1-4의 "이미 최신" 조기 종료 조건(`incr_from > new_to`)이
GA4 기준으로만 판단하기 때문에 **일반 재실행으로는 DB가 영영 안 채워진다**(다음날 GA4
범위가 하루 더 늘어나면 그때는 전체 기간 재조회에 DB도 묻어가면서 저절로 채워지지만,
당일 안에 채우려면 일반 재실행으로는 안 됨). 이럴 때는 §1-§5 전체를 건너뛰고 바로:
```
python3 scripts/update_ga4_ainote_kpi_unsedang.py --html html/ga4-ainote-kpi-unsedang.html --db-only
```
를 실행한다(`--indir` 불필요, GA4/DATE_RANGE는 전혀 건드리지 않고 DB API 6개 지표만
START_DATE~기존 DATE_RANGE.to로 재조회해 채운다). 먼저 네트워크 확인:
`curl -s -o /dev/null -w '%{http_code}\n' "https://adm.unsedang.com/api/v1/reports/consultation-stats/monthly?baseMonth=<YYYY-MM>"`
가 200이면 시도할 가치가 있다.

## §1 사전 확인

1. `get_today` 툴을 호출해 오늘 날짜를 확정한다.
2. `grep -n "const DATE_RANGE" html/ga4-ainote-kpi-unsedang.html`로 현재 범위
   (`DATE_RANGE.from` ~ `DATE_RANGE.to`)를 읽는다.
3. 종료일 결정: `$ARGUMENTS`에 `--to YYYY-MM-DD`가 있으면 그 값, 없으면 **어제**(D-1,
   `new_to`). 시작일은 항상 `2026-09-30`로 고정(`new_from`).
4. `incr_from = (기존 DATE_RANGE.to) + 1일`. `incr_from > new_to`이면 **"이미 최신
   상태입니다(마지막 수록일 {DATE_RANGE.to})"라고 보고하고 쿼리 없이 즉시 종료**한다.
5. **샤드 가용성 확인** — `execute_sql_readonly`로 아래 쿼리 실행(메타데이터 조회라 비용 0):
   ```sql
   SELECT COUNT(*) AS n_shards, MIN(table_id) AS first_shard, MAX(table_id) AS last_shard
   FROM `unsedang.analytics_488612198.__TABLES__`
   WHERE REGEXP_CONTAINS(table_id, r'^events_\d{8}$')
     AND SUBSTR(table_id, 8) BETWEEN '<incr_from을 YYYYMMDD로>' AND '<new_to를 YYYYMMDD로>'
   ```
   `last_shard`가 `events_<new_to의 YYYYMMDD>`가 아니면 **중단**하고 "BigQuery 일별 export가
   아직 D-1(`new_to`) 샤드를 만들지 않았습니다. 잠시 후 재실행하거나 `--to <D-2>`로 명시
   실행하세요."라고 보고한다. `n_shards`가 날짜 수와 다르면(구멍) 어느 날짜가 비었는지
   목록을 뽑아 보고하고 **중단**한다. `events_intraday_*`는 이 정규식에 걸리지 않으므로
   쓰지 않는다.
6. `$ARGUMENTS`에 `--dry-run`이 있으면 §5에서 스크립트를 `--dry-run`으로만 실행한다.

## §2 증분 쿼리 7건 (기간: `incr_from` ~ `new_to` — 보통 하루치)

아래 SQL 파일을 Read하고 `{{FROM}}`/`{{TO}}`를 `incr_from`/`new_to`(YYYYMMDD, 대시 없이)로,
`{{EVENT_PREDICATE}}`가 있는 파일은 해당 표의 값으로 치환한 뒤
`execute_sql_readonly(projectId='unsedang', query=<치환된 SQL>)`로 실행한다.

| 쿼리 | SQL 파일 | `{{EVENT_PREDICATE}}` (해당 시) | 출력 열 |
|---|---|---|---|
| 1 상담하기(선불+후불) | `scripts/sql/event_users_daily.sql` | `event_name IN ('pre_tel_click', 'post_tel_click')` | `date, activeUsers` |
| 2 상담하기(선불만) | `scripts/sql/event_users_daily.sql` | `event_name = 'pre_tel_click'` | `date, activeUsers` |
| 3 AI노트 페이지 2종 | `scripts/sql/ainote_pages_daily.sql` | (고정, 파일 안에 하드코딩) | `date, path, activeUsers` |
| 4 추적 이벤트 7종 | `scripts/sql/ainote_subevents_daily.sql` | (고정) | `date, eventName, activeUsers` |
| 5 노트 상세 참여시간 | `scripts/sql/ainote_engagement_daily.sql` | (고정, `/view/ai-note/noteInfo`) | `date, totalEngagementDuration, activeUsers` |
| 6 알림톡 UTM 클릭 | `scripts/sql/ainote_utmclick_daily.sql` | (고정, 세션 스코프 필터 — naver-powerlink 패턴) | `date, activeUsers` |
| 13 선생님 추천 클릭 | `scripts/sql/event_users_daily.sql` | `REGEXP_CONTAINS(event_name, r'callnote_reco_click')` | `date, activeUsers` |

## §3 기간 전체 쿼리 7건 (비집계 지표라 필수 — 생략 금지, 기간: `new_from`(2026-09-30) ~ `new_to`)

대응하는 `_period.sql` 파일을 `{{FROM}}=new_from`, `{{TO}}=new_to`로 치환해 실행한다
(이 파일들은 애초에 `date` dimension이 없다).

| 쿼리 | SQL 파일 | `{{EVENT_PREDICATE}}` (해당 시) | 출력 열 |
|---|---|---|---|
| 7 상담하기(선불+후불) 기간 합계 | `scripts/sql/event_users_period.sql` | 쿼리 1과 동일 | `activeUsers` (한 행) |
| 8 상담하기(선불만) 기간 합계 | `scripts/sql/event_users_period.sql` | 쿼리 2와 동일 | `activeUsers` (한 행) |
| 9 페이지 2종 기간 합계 | `scripts/sql/ainote_pages_period.sql` | — | `path, activeUsers` |
| 10 추적 이벤트 7종 기간 합계 | `scripts/sql/ainote_subevents_period.sql` | — | `eventName, activeUsers` |
| 11 참여시간 기간 합계 | `scripts/sql/ainote_engagement_period.sql` | — | `totalEngagementDuration, activeUsers` (한 행) |
| 12 UTM 클릭 기간 합계 | `scripts/sql/ainote_utmclick_period.sql` | — | `activeUsers` (한 행) |
| 14 선생님 추천 클릭 기간 합계 | `scripts/sql/event_users_period.sql` | 쿼리 13과 동일 | `activeUsers` (한 행) |

> 왜 매번 기간 전체를 다시 물어보는가? `activeUsers`는 비집계 지표라 일별 값을 더하면
> 실제보다 부풀려진다. 창이 하루 늘 때마다 전체 누적 기간 기준으로 순사용자 수를 처음부터
> 다시 계산해야 정확하다.

> 검증 기록(`docs/bigquery-ga4-mapping.md` §6-2): 2026-09-30~10-13 전체 기간을 BQ로 재현한
> 결과 `CALL_TOTAL`/`PRETEL_TOTAL`/`PAGE_TOTALS.noteInfo`/`ENGAGEMENT_TOTAL.users`/
> `RECO_CLICK_TOTAL`/`SUBEVENT_TOTALS` 7종 전부 기존 Supermetrics 값과 **완전 일치**했고,
> `PAGE_TOTALS.aiNote`(3.5%)·`ENGAGEMENT_TOTAL.duration`(1.6%)만 작은 오차가 있었다.

## §4 임시 JSON 저장

`mkdir -p /tmp/ga4-ainote-kpi-update/<YYYYMMDD-HHMMSS>/` 후 아래 14개 파일을 Write
(DB API 쪽 4개 필드는 스크립트가 직접 호출하므로 여기서 스테이징하지 않는다):

- `call_incremental.json` / `call_period.json`: `{"rows":[{"date","activeUsers"}]}` (쿼리1/7)
- `pretel_incremental.json` / `pretel_period.json`: 동일 스키마 (쿼리2/8)
- `pages_incremental.json`: `{"rows":[{"date","path","activeUsers"}]}` (쿼리3)
- `pages_period.json`: `{"rows":[{"path","activeUsers"}]}` (쿼리9)
- `subevents_incremental.json`: `{"rows":[{"date","eventName","activeUsers"}]}` (쿼리4)
- `subevents_period.json`: `{"rows":[{"eventName","activeUsers"}]}` (쿼리10)
- `engagement_incremental.json`: `{"rows":[{"date","totalEngagementDuration","activeUsers"}]}` (쿼리5 —
  SQL이 이미 `totalEngagementDuration` 열 이름으로 돌려준다, 초 단위)
- `engagement_period.json`: `{"rows":[{"totalEngagementDuration","activeUsers"}]}` (쿼리11, 한 행)
- `utmclick_incremental.json` / `utmclick_period.json`: `{"rows":[{"date","activeUsers"}]}` /
  `{"rows":[{"activeUsers"}]}` (쿼리6/12, period는 한 행)
- `recoclick_incremental.json` / `recoclick_period.json`: 동일 스키마 (쿼리13/14, 선생님
  추천 버튼 클릭, 06 보조지표 — 트래픽이 적어 결측일이 정상)

값이 0이거나 BigQuery 응답에 없던 날짜/경로/이벤트는 행을 만들지 않아도 된다(희소 저장
방식 — 특히 추적 이벤트 7종은 트래픽이 적어 결측이 정상).

## §5 스크립트 실행

먼저 진단만:
```
python3 scripts/update_ga4_ainote_kpi_unsedang.py --html html/ga4-ainote-kpi-unsedang.html --indir <tmpdir> --to <new_to> --dry-run
```
출력된 요약(새 범위, 각 지표 기간 합계, DB API 기간 합계, 경고)을 확인한 뒤 `--dry-run`을
떼고 재실행한다. `$ARGUMENTS`에 `--skip-db`가 있으면 그대로 전달한다.

`[SafetyError]`로 중단되면 **절대 우회하지 말고** 에러 메시지를 그대로 사용자에게 보고하고
원인을 파악한다 — HTML 블록을 못 찾음, 음수 값, 신규 데이터 0건, DB API 호출 실패, 알 수
없는 페이지 경로/eventName 등 실제 데이터 무결성 문제다. 새 페이지 경로/이벤트가 필요해지면
(신규 기능 추가) 스크립트의 `PAGE_PATH_TO_KEY`/`SUBEVENT_KEYS`와 HTML을 사람이 먼저 함께
갱신해야 한다 — 이 커맨드만으로는 처리할 수 없다.

## §6 렌더 검증 — 기본 생략

이 커맨드는 기본적으로 데이터 갱신까지만 하고 브라우저 렌더 확인은 생략한다. 사용자가
명시적으로 요청할 때만 Playwright로 확인하고, `.playwright-mcp/` 산출물은 확인 직후 삭제한다.

## §7 무인 스케줄 실행 시 (routine으로 호출된 경우)

사용자 확인을 기다리지 말고 끝까지 자동으로 진행한다:
- 이미 최신이면(§1-4) 아무 파일도 건드리지 말고 그대로 종료한다.
- 갱신됐다면 `git add html/ga4-ainote-kpi-unsedang.html daylog/<오늘 날짜>.md` / commit
  (메시지: `"AI상담노트 KPI 리포트 자동 업데이트: <이전 범위> -> <새 범위>"`) / push까지
  반드시 완료한다. 저장소는 `origin/main`에 이미 연결돼 있다.
- `[SafetyError]`로 중단되면(DB API 호출 실패 포함) 우회 플래그 없이, 무엇이 왜 실패했는지
  세션 결과에 명확히 남기고 커밋 없이 종료한다. DB API 호출이 일시적으로 실패하면
  `--skip-db`로 재시도할지, 그냥 실패로 두고 다음 실행을 기다릴지는 에러 성격에 따라
  판단한다 — 반복 실패가 아니라면 그냥 실패로 두고 다음날 재시도가 안전하다.

## §8 보고 + daylog

1. 스크립트 출력 요약(이전 범위 → 새 범위, 각 지표 기간 합계, 경고)을 사용자에게 전달한다.
2. §0의 원칙 문구(누적형, DAILY_AINOTE_USAGE는 수동)를 함께 안내한다.
3. **이 커맨드는 실행할 때마다** `daylog/<오늘 날짜>.md`에 append한다:
   ```markdown
   ## <오늘 날짜> 핸드오프 — AI상담노트 KPI 리포트 누적 업데이트
   - 한 일: /update-ga4-ainote-kpi-unsedang 실행, {이전 범위} -> {새 범위} 갱신
   - 변경 파일: html/ga4-ainote-kpi-unsedang.html
   - 다음: 특이사항 없음 (또는 스크립트 경고 내용 요약)
   ```
   파일이 없으면 CLAUDE.md 규약대로 머리말을 붙여 새로 만든다.
