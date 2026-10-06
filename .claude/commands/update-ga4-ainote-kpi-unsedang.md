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
1. **GA4(Supermetrics/GAWA)** — CALL/PRETEL/PAGES(aiNote·noteInfo)/SUBEVENTS(7종)/
   ENGAGEMENT/UTM_CLICK. `scripts/update_ga4_ainote_kpi_unsedang.py`는 Supermetrics를
   직접 호출하지 않는다(에이전트만 MCP 툴 호출 가능) — 이 커맨드(에이전트)가 미리 JSON
   파일로 떠서 `--indir`에 넣어두면 스크립트가 읽는다. 기간 합계는 "새 날짜만 반영"이
   아니라 **매번 전체 누적 기간을 재조회한 값으로 통째로 교체**한다(activeUsers는 비집계
   지표).
2. **운세당 DB API**(`consultation-stats/monthly`) — ALIMTALK/AINOTE_CONSULT_CNT/
   AINOTE_CONSULT_USR/AINOTE_REPEAT_USR(전부 선불 전용, 후불은 항상 0). 이 API는 인증
   없는 공개 CORS API라 **스크립트가 직접 호출**한다 — 이 커맨드가 따로 조회할 필요
   없다. 네트워크 문제 등으로 DB 쪽만 건너뛰어야 하면 `--skip-db`를 전달한다.

**`DAILY_AINOTE_USAGE`는 이 스크립트가 절대 건드리지 않는다** — 운영진이 직접 전달하는
수동 실집계(자동 수집 경로 없음). 새 날짜가 생겨도 값이 없으면 그냥 0으로 표시될 뿐
(보조지표, 목표 없음) 판정에 영향 없다. 새 값이 생기면 사람이 직접
`DAILY_AINOTE_USAGE` 딕셔너리에 추가해야 한다 — 이 커맨드의 책임이 아니다.

이 커맨드가 실제로 Supermetrics를 호출하는 건 여기(에이전트)뿐이다.
`scripts/update_ga4_ainote_kpi_unsedang.py`는 GA4 쪽 병합/재작성만 담당하고, DB API
쪽은 스크립트 자신이 직접 호출한다.

## §1 사전 확인

1. `get_today` 툴을 호출해 오늘 날짜를 확정한다.
2. `grep -n "const DATE_RANGE" html/ga4-ainote-kpi-unsedang.html`로 현재 범위
   (`DATE_RANGE.from` ~ `DATE_RANGE.to`)를 읽는다.
3. 종료일 결정: `$ARGUMENTS`에 `--to YYYY-MM-DD`가 있으면 그 값, 없으면 **어제**(D-1,
   `new_to`). 시작일은 항상 `2026-09-30`로 고정(`new_from`).
4. `incr_from = (기존 DATE_RANGE.to) + 1일`. `incr_from > new_to`이면 **"이미 최신
   상태입니다(마지막 수록일 {DATE_RANGE.to})"라고 보고하고 쿼리 없이 즉시 종료**한다.
5. `$ARGUMENTS`에 `--dry-run`이 있으면 §5에서 스크립트를 `--dry-run`으로만 실행한다.

## §2 증분 쿼리 6건 (기간: `incr_from` ~ `new_to` — 보통 하루치)

`ds_id='GAWA'`, `ds_accounts='488612198'`, `date_range_type='custom'`,
`start_date=incr_from`, `end_date=new_to`.

**쿼리 1 — 상담하기(선불+후불 합산)**
- fields: `date,activeUsers`
- filter: `eventName == 'pre_tel_click' OR eventName == 'post_tel_click'`

**쿼리 2 — 상담하기(선불만)**
- fields: `date,activeUsers`
- filter: `eventName == 'pre_tel_click'`

**쿼리 3 — AI 상담노트 페이지 2종**
- fields: `date,pagePathWithoutQueryString,activeUsers`
- filter: `pagePathWithoutQueryString == '/view/ai-note' OR pagePathWithoutQueryString == '/view/ai-note/noteInfo'`

**쿼리 4 — 추적 이벤트 7종**
- fields: `date,eventName,activeUsers`
- filter (IN-list, 문자 그대로 복사):
  ```
  eventName [] ["ai-note-agree-pop","ai-note-cancel-click","ai-note-agree-click","ai-note-review-skip","ai-note-review-next","ai-note-review-submit","ai-note-councel-click"]
  ```

**쿼리 5 — 노트 상세 참여시간**
- fields: `date,userEngagementDuration,activeUsers`
- filter: `pagePathWithoutQueryString == '/view/ai-note/noteInfo'`

**쿼리 6 — 알림톡 "바로가기" UTM 클릭**
- fields: `date,activeUsers`
- filter: `sessionSource == 'kakao_alimtalk' AND sessionMedium == 'push' AND sessionCampaignName == 'callnote_created'`

응답이 비동기(`schedule_id`)면 `get_async_query_results`로 완료까지 폴링한다.

## §3 기간 전체 쿼리 6건 (비집계 지표라 필수 — 생략 금지, 기간: `new_from`(2026-09-30) ~ `new_to`)

`date_range_type='custom'`, `start_date=new_from`, `end_date=new_to`. **dimension에서
`date`를 뺀다.**

**쿼리 7 — 상담하기(선불+후불) 기간 합계**: fields `activeUsers`, filter는 쿼리 1과 동일
**쿼리 8 — 상담하기(선불만) 기간 합계**: fields `activeUsers`, filter는 쿼리 2와 동일
**쿼리 9 — 페이지 2종 기간 합계**: fields `pagePathWithoutQueryString,activeUsers`, filter는 쿼리 3과 동일
**쿼리 10 — 추적 이벤트 7종 기간 합계**: fields `eventName,activeUsers`, filter는 쿼리 4와 동일
**쿼리 11 — 참여시간 기간 합계**: fields `userEngagementDuration,activeUsers`, filter는 쿼리 5와 동일
**쿼리 12 — UTM 클릭 기간 합계**: fields `activeUsers`, filter는 쿼리 6과 동일

> 왜 매번 기간 전체를 다시 물어보는가? `activeUsers`는 비집계 지표라 일별 값을 더하면
> 실제보다 부풀려진다. 창이 하루 늘 때마다 전체 누적 기간 기준으로 순사용자 수를 처음부터
> 다시 계산해야 정확하다.

## §4 임시 JSON 저장

`mkdir -p /tmp/ga4-ainote-kpi-update/<YYYYMMDD-HHMMSS>/` 후 아래 12개 파일을 Write
(DB API 쪽 4개 필드는 스크립트가 직접 호출하므로 여기서 스테이징하지 않는다):

- `call_incremental.json` / `call_period.json`: `{"rows":[{"date","activeUsers"}]}` (쿼리1/7)
- `pretel_incremental.json` / `pretel_period.json`: 동일 스키마 (쿼리2/8)
- `pages_incremental.json`: `{"rows":[{"date","path","activeUsers"}]}` (쿼리3)
- `pages_period.json`: `{"rows":[{"path","activeUsers"}]}` (쿼리9)
- `subevents_incremental.json`: `{"rows":[{"date","eventName","activeUsers"}]}` (쿼리4)
- `subevents_period.json`: `{"rows":[{"eventName","activeUsers"}]}` (쿼리10)
- `engagement_incremental.json`: `{"rows":[{"date","totalEngagementDuration","activeUsers"}]}` (쿼리5 —
  `userEngagementDuration` 필드값을 `totalEngagementDuration` 키로 저장)
- `engagement_period.json`: `{"rows":[{"totalEngagementDuration","activeUsers"}]}` (쿼리11, 한 행)
- `utmclick_incremental.json` / `utmclick_period.json`: `{"rows":[{"date","activeUsers"}]}` /
  `{"rows":[{"activeUsers"}]}` (쿼리6/12, period는 한 행)

값이 0이거나 GA4 응답에 없던 날짜/경로/이벤트는 행을 만들지 않아도 된다(희소 저장 방식 —
특히 추적 이벤트 7종은 트래픽이 적어 결측이 정상).

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
