---
description: 운세당 매체별 유입 리포트(html/ga4-channel-unsedang.html)를 "최근 2주" 롤링 윈도우로 매일 갱신한다(오래된 날짜는 밀려나고 최신 날짜가 추가됨). 퍼널 리포트와 달리 누적형이 아니다.
argument-hint: "[--to YYYY-MM-DD] [--dry-run]"
---

# 매체별 유입 리포트 롤링 업데이트 (운세당)

인자: `$ARGUMENTS`

## §0 목적과 절대 원칙 (반드시 지킬 것)

이 커맨드는 `html/ga4-channel-unsedang.html`을 **항상 "최근 14일" 창으로 유지**한다.
`html/ga4-funnel-unsedang.html`(퍼널 리포트, `/update-ga4-unsedang`)과는 갱신 철학이
근본적으로 다르다 — 그 리포트는 날짜를 영구 누적하지만, 이 리포트는 매 실행마다:

1. 새로 확정된 날짜(들)를 추가하고
2. 창 밖으로 밀려난 오래된 날짜를 제거하고(항상 14일 유지)
3. **그룹별/기간 합계(`REFERRER_TOTALS`, `ETC_BREAKDOWN`, `TOTAL_PERIOD`)는 새 창 전체를
   다시 조회한 값으로 통째로 교체**한다 — activeUsers는 비집계 지표라 오래된 값을 재사용할
   수 없기 때문이다.

이 문구는 §9에서 사용자에게 그대로 전달한다.

**배열 순서**: `REFERRER_DAILY`의 `[a,b]` = `[활성사용자, 세션]`.

**새 sessionSource 값이 나타나면 자동 처리되지 않는다.** `scripts/update_ga4_channel_unsedang.py`의
`GROUP_DAILY_KEYS`/`ETC_ITEM_KEYS`/`NAVER_SUB_LABELS`/`GOOGLE_SUB_LABELS`에 없는 값이 쿼리
결과에 나오면 `[SafetyError]`로 중단된다. 이 경우 ①해당 매핑 테이블에 새 값 추가, ②
`html/ga4-channel-unsedang.html`의 `REFERRER_GROUPS`(신규 그룹이면) 또는 `ETC_BREAKDOWN`
라벨(기존 "기타" 그룹에 편입시키는 경우) 수동 반영, ③ 신규 그룹이면 CSS 색상 토큰(s6) 추가가
먼저 필요하다 — 절대 임의로 기존 그룹에 합치거나 건너뛰지 말고 사용자에게 보고한다.

이 커맨드가 실제로 Supermetrics를 호출하는 건 여기(에이전트)뿐이다.
`scripts/update_ga4_channel_unsedang.py`는 병합/윈도우 슬라이딩/재작성만 담당하며 MCP를
호출하지 않는다.

## §1 사전 확인

1. `get_today` 툴을 호출해 오늘 날짜를 확정한다.
2. `grep -n "const DATE_RANGE" html/ga4-channel-unsedang.html`로 현재 창(`DATE_RANGE.from`
   ~ `DATE_RANGE.to`)을 읽는다.
3. 종료일 결정: `$ARGUMENTS`에 `--to YYYY-MM-DD`가 있으면 그 값, 없으면 **어제**
   (`new_to`). `new_from = new_to - 13일`.
4. `incr_from = (기존 DATE_RANGE.to) + 1일`. `incr_from > new_to`이면 **"이미 최신
   상태입니다(마지막 수록일 {DATE_RANGE.to})"라고 보고하고 쿼리 없이 즉시 종료**한다.
5. `$ARGUMENTS`에 `--dry-run`이 있으면 §7에서 스크립트를 `--dry-run`으로만 실행한다.

## §2 증분 쿼리 5건 (기간: `incr_from` ~ `new_to` — 보통 하루치)

`ds_id='GAWA'`, `ds_accounts='488612198'`, `date_range_type='custom'`,
`start_date=incr_from`, `end_date=new_to`로 아래 5개 쿼리를 실행한다.

**쿼리 1 — 원본 채널 전체(그룹핑 없음)**
- fields: `date,sessionSource,activeUsers,sessions`
- filter: 없음

**쿼리 2 — 네이버 병합**
- fields: `date,activeUsers,sessions`
- filter: `sessionSource == 'naver' OR sessionSource == 'navercafe' OR sessionSource == 'm.search.naver.com' OR sessionSource == 'm.naver.com' OR sessionSource == 'nid.naver.com'`

**쿼리 3 — 구글 병합**
- fields: `date,activeUsers,sessions`
- filter: `sessionSource == 'google' OR sessionSource == 'google-play'`

**쿼리 4 — 기타 병합**
- fields: `date,activeUsers,sessions`
- filter: `sessionSource == 'payments.danalpay.com' OR sessionSource == 'kauth.kakao.com' OR sessionSource == 'accounts.kakao.com' OR sessionSource == 'unsedang_portal' OR sessionSource == 'banner_01' OR sessionSource == 'chatgpt.com'`

**쿼리 5 — 사이트 전체(합계 열)**
- fields: `date,activeUsers`
- filter: 없음

응답이 비동기(`schedule_id`)면 `get_async_query_results`로 완료까지 폴링한다.

## §3 기간 전체 쿼리 5건 (비집계 지표라 필수 — 생략 금지, 기간: `new_from` ~ `new_to`)

`date_range_type='custom'`, `start_date=new_from`, `end_date=new_to`. **dimension에서
`date`를 빼고** 아래 5개를 실행한다.

**쿼리 6 — 원본 채널 전체 기간 합계**
- fields: `sessionSource,activeUsers,sessions`
- filter: 없음
- (여기서 LG/`(not set)`/`(direct)` 3개 행과, "기타" 6개 항목 각각의 기간 합계를
  한 번에 얻는다 — 나머지 행(네이버/구글 서브소스)은 버린다.)

**쿼리 7 — 네이버 병합 기간 합계**: fields `activeUsers`, filter = §2 쿼리2와 동일
**쿼리 8 — 구글 병합 기간 합계**: fields `activeUsers`, filter = §2 쿼리3과 동일
**쿼리 9 — 기타 병합 기간 합계**: fields `activeUsers`, filter = §2 쿼리4와 동일
**쿼리 10 — 사이트 전체 기간 합계**: fields `activeUsers`, filter 없음

> 왜 매번 기간 전체를 다시 물어보는가? `activeUsers`는 비집계 지표라 일별 값을 더하면
> 실제보다 부풀려진다. 이 리포트는 누적이 아니라 "최근 14일" 롤링 창이므로, 창이 하루
> 밀릴 때마다 그룹별·전체 순사용자 수를 처음부터 다시 계산해야 정확하다.

## §4 임시 JSON 저장

`mkdir -p /tmp/ga4-channel-update/<YYYYMMDD-HHMMSS>/` 후 아래 10개 파일을 Write:

- `raw_incremental.json`: `{"rows":[{"date","channel","activeUsers","sessions"}, ...]}` (쿼리1)
- `naver_daily.json` / `google_daily.json` / `etc_daily.json`: `{"rows":[{"date","activeUsers","sessions"}, ...]}` (쿼리2/3/4)
- `total_daily.json`: `{"rows":[{"date","activeUsers"}, ...]}` (쿼리5)
- `raw_period.json`: `{"rows":[{"channel","activeUsers","sessions"}, ...]}` (쿼리6)
- `naver_period.json` / `google_period.json` / `etc_period.json`: `{"rows":[{"activeUsers": N}]}` (쿼리7/8/9, **한 행만**)
- `total_period.json`: `{"rows":[{"activeUsers": N}]}` (쿼리10, **한 행만**)

`channel` 필드는 GA4가 반환한 표시값 그대로 쓴다(예: `'LG'`, `'(not set)'`, `'(direct)'`,
`'payments.danalpay.com'` 등) — 가공하지 말 것. 값이 0이거나 GA4 응답에 없던 날짜/채널은
행을 만들지 않는다.

## §5 스크립트 실행

먼저 진단만:
```
python3 scripts/update_ga4_channel_unsedang.py --html html/ga4-channel-unsedang.html --indir <tmpdir> --dry-run
```
출력된 요약(새 창 범위, 그룹별/전체 기간 합계, 경고)을 확인한 뒤 `--dry-run`을 떼고 재실행한다.

`[SafetyError]`로 중단되면 **절대 우회하지 말고** 에러 메시지를 그대로 사용자에게
보고하고 원인을 파악한다(신규 sessionSource 값, 쿼리 실패, 검증 실패 등).

## §6 렌더 검증 — 기본 생략

이 커맨드는 기본적으로 데이터 갱신까지만 하고 브라우저 렌더 확인은 생략한다. 사용자가
명시적으로 요청할 때만 Playwright로 확인하고, `.playwright-mcp/` 산출물은 확인 직후 삭제한다.

## §7 상담수/전환율 — 손대지 않는다

`html/ga4-channel-unsedang.html`의 "상담수"/"전환율" 열은 브라우저가 페이지를 열 때마다
`CONSULT_API`(사내 DB API)에서 실시간으로 fetch한다. 이 커맨드/스크립트는 정적 스냅샷인
GA4 데이터(`REFERRER_DAILY`/`REFERRER_TOTALS`/`ETC_BREAKDOWN`/`TOTAL_DAILY`/`TOTAL_PERIOD`)만
다루며, 상담수 관련 코드는 절대 건드리지 않는다.

## §8 무인 스케줄 실행 시 (routine으로 호출된 경우)

사용자 확인을 기다리지 말고 끝까지 자동으로 진행한다:
- 이미 최신이면(§1-4) 아무 파일도 건드리지 말고 그대로 종료한다.
- 갱신됐다면 `git add html/ga4-channel-unsedang.html daylog/<오늘 날짜>.md` / commit
  (메시지: `"매체별 유입 리포트 자동 업데이트: <이전 창> -> <새 창>"`) / push까지 반드시
  완료한다. 저장소는 `origin/main`에 이미 연결돼 있다.
- `[SafetyError]`로 중단되면 우회 플래그 없이, 무엇이 왜 실패했는지 세션 결과에 명확히
  남기고 커밋 없이 종료한다.

## §9 보고 + daylog

1. 스크립트 출력 요약(이전 창 → 새 창, 그룹별/전체 기간 합계, 경고)을 사용자에게 전달한다.
2. §0의 원칙 문구를 함께 안내한다.
3. **이 커맨드는 실행할 때마다** `daylog/<오늘 날짜>.md`에 append한다:
   ```markdown
   ## <오늘 날짜> 핸드오프 — 매체별 유입 리포트 롤링 업데이트
   - 한 일: /update-ga4-channel-unsedang 실행, {이전 창} -> {새 창} 갱신
   - 변경 파일: html/ga4-channel-unsedang.html
   - 다음: 특이사항 없음 (또는 스크립트 경고 내용 요약)
   ```
   파일이 없으면 CLAUDE.md 규약대로 머리말을 붙여 새로 만든다.
