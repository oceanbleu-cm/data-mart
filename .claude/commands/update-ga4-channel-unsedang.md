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
3. **그룹별/기간 합계(`FIRST_USER_TOTALS`, `TOTAL_PERIOD`)는 새 창 전체를 다시 조회한
   값으로 통째로 교체**한다 — activeUsers는 비집계 지표라 오래된 값을 재사용할 수 없기
   때문이다.

이 문구는 §8에서 사용자에게 그대로 전달한다.

**2026-09-30 리디자인(커밋 `110c44a`)으로 이 페이지의 구조가 바뀌었다.** 이전에는
"레퍼러 도메인 그룹"(sessionSource 기준)과 "첫 사용자 소스 그룹"(firstUserSource 기준)
두 섹션이 있었지만, 레퍼러 도메인 그룹 섹션(`REFERRER_DAILY`/`REFERRER_TOTALS`/
`ETC_BREAKDOWN`)은 **의도적으로 삭제**됐고 지금은 **"첫 사용자 소스 그룹"
(`FIRST_USER_DAILY`/`FIRST_USER_TOTALS`, GA4 `firstUserSource` 기준) 섹션만 남아 있다**
(2026-10-01, 이 사실을 스크립트/커맨드 문서에 반영하지 않아 자동 routine이 매일
`[SafetyError] REFERRER_DAILY 블록을 찾지 못했습니다`로 실패하던 것을 발견해 수정함).
firstUserSource는 사용자당 평생 하나뿐인 값이라 원본 값을 **단순 합산**하면 되고(GA4도
세션 소스 방식 필터 재조회를 firstUserSource에는 거부한다), 병합 쿼리가 필요 없다.
`TOTAL_DAILY`/`TOTAL_PERIOD`(사이트 전체, attribution 기준과 무관)는 소스 필터 없이
별도로 재조회한 값을 그대로 공유한다.

**배열 순서**: `FIRST_USER_DAILY`의 `[a,b]` = `[활성사용자, 세션]`.

**새 firstUserSource 값은 자동으로 분류된다(SafetyError로 중단되지 않는다).**
`scripts/update_ga4_channel_unsedang.py`의 `FIRST_USER_LABEL_TO_GROUP`에 없는 값이
나오면 `classify_source()`가 다음 규칙으로 자동 분류한다: 원본 값에 `'naver'`가
포함되면(대소문자 무시) `naverGrp`, `'google'`이 포함되면 `googleGrp`, `'(not set)'`이거나
`''`(빈 문자열)이면 `notSet`, 그 외 전부 `etcGrp`. 분류 결과는 스크립트 출력의 "경고"
목록에 남으므로 §8에서 사용자에게 그대로 전달해 사후 확인할 수 있게 한다(자동 분류가
틀렸다고 판단되면 `FIRST_USER_LABEL_TO_GROUP`에 정식으로 추가해 다음부터 그 값이 "신규"로
잡히지 않게 한다 — 급한 조치는 아니다). firstUserSource는 원본 값을 그냥 합산하므로
sessionSource와 달리 병합 쿼리 필터를 동적으로 구성할 필요가 없다 — 자동 분류만으로
즉시 정확하다.

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
5. `$ARGUMENTS`에 `--dry-run`이 있으면 §5에서 스크립트를 `--dry-run`으로만 실행한다.

## §2 증분 쿼리 2건 (기간: `incr_from` ~ `new_to` — 보통 하루치)

`ds_id='GAWA'`, `ds_accounts='488612198'`, `date_range_type='custom'`,
`start_date=incr_from`, `end_date=new_to`로 아래 2개 쿼리를 실행한다.

**쿼리 1 — 사이트 전체(합계 열, 소스 필터 없음)**
- fields: `date,activeUsers`
- filter: 없음

**쿼리 2 — 첫 사용자 소스 전체(그룹핑 없음, firstUserSource)**
- fields: `date,firstUserSource,activeUsers,sessions`
- filter: 없음
- (이 값은 병합 쿼리가 필요 없다 — §0 참고. `scripts/update_ga4_channel_unsedang.py`가
  `FIRST_USER_LABEL_TO_GROUP` + `classify_source()` 자동 분류로 그룹별 합산한다 — 여기는
  동적 필터를 만들 필요 없이 원본 그대로 저장하면 된다.)

응답이 비동기(`schedule_id`)면 `get_async_query_results`로 완료까지 폴링한다.

## §3 기간 전체 쿼리 2건 (비집계 지표라 필수 — 생략 금지, 기간: `new_from` ~ `new_to`)

`date_range_type='custom'`, `start_date=new_from`, `end_date=new_to`. **dimension에서
`date`를 뺀다.**

**쿼리 3 — 사이트 전체 기간 합계**: fields `activeUsers`, filter 없음

**쿼리 4 — 첫 사용자 소스 전체 기간 합계(firstUserSource)**
- fields: `firstUserSource,activeUsers,sessions`
- filter: 없음
- (병합 쿼리 없이 이 한 건으로 6개 그룹의 기간 합계를 전부 합산해서 만든다 —
  `scripts/update_ga4_channel_unsedang.py`가 자동 분류까지 포함해 정확히 처리한다.)

> 왜 매번 기간 전체를 다시 물어보는가? `activeUsers`는 비집계 지표라 일별 값을 더하면
> 실제보다 부풀려진다. 이 리포트는 누적이 아니라 "최근 14일" 롤링 창이므로, 창이 하루
> 밀릴 때마다 그룹별·전체 순사용자 수를 처음부터 다시 계산해야 정확하다. firstUserSource는
> 원본 값 합산 자체가 정확하지만(§0), 그래도 "새 윈도우 전체" 기준으로 다시 합산해야 하는
> 것은 동일하다 — 일별 합산은 기간 dedup과 다르다(재방문자 중복).

## §4 임시 JSON 저장

`mkdir -p /tmp/ga4-channel-update/<YYYYMMDD-HHMMSS>/` 후 아래 4개 파일을 Write:

- `total_daily.json`: `{"rows":[{"date","activeUsers"}, ...]}` (쿼리1)
- `firstuser_raw_incremental.json`: `{"rows":[{"date","source","activeUsers","sessions"}, ...]}` (쿼리2)
- `total_period.json`: `{"rows":[{"activeUsers": N}]}` (쿼리3, **한 행만**)
- `firstuser_raw_period.json`: `{"rows":[{"source","activeUsers","sessions"}, ...]}` (쿼리4)

`source` 필드는 GA4가 반환한 표시값 그대로 쓴다(예: `'LG'`, `'(not set)'`, `'(direct)'`,
`'m.search.naver.com'` 등) — 가공하지 말 것. 값이 0이거나 GA4 응답에 없던 날짜/값은 행을
만들지 않는다.

## §5 스크립트 실행

먼저 진단만:
```
python3 scripts/update_ga4_channel_unsedang.py --html html/ga4-channel-unsedang.html --indir <tmpdir> --dry-run
```
출력된 요약(새 창 범위, 그룹별/전체 기간 합계, 경고)을 확인한 뒤 `--dry-run`을 떼고 재실행한다.
신규 값 자동 분류는 "경고"로만 표시되고 실행을 막지 않는다(§0) — 정상 진행한다.

`[SafetyError]`로 중단되면 **절대 우회하지 말고** 에러 메시지를 그대로 사용자에게
보고하고 원인을 파악한다. 신규 firstUserSource 값은 이 에러의 원인이 아니다(자동 분류로
대체됨) — 남아있는 SafetyError는 HTML 블록을 못 찾음(예: 또 구조가 바뀜), 윈도우 밖 날짜
잔존, 음수 값, 신규 일별 데이터 0건, 쿼리 결과 없음 등 실제 데이터 무결성 문제다.

## §6 렌더 검증 — 기본 생략

이 커맨드는 기본적으로 데이터 갱신까지만 하고 브라우저 렌더 확인은 생략한다. 사용자가
명시적으로 요청할 때만 Playwright로 확인하고, `.playwright-mcp/` 산출물은 확인 직후 삭제한다.

## §7 상담수/전환율 — 손대지 않는다

`html/ga4-channel-unsedang.html`의 "상담수"/"전환율"/"상담인원" 열은 브라우저가 페이지를
열 때마다 `CONSULT_API`(사내 DB API)에서 실시간으로 fetch한다. 이 커맨드/스크립트는
정적 스냅샷인 GA4 데이터(`FIRST_USER_DAILY`/`FIRST_USER_TOTALS`/`TOTAL_DAILY`/
`TOTAL_PERIOD`)만 다루며, 상담수 관련 코드는 절대 건드리지 않는다.

## §8 무인 스케줄 실행 시 (routine으로 호출된 경우)

사용자 확인을 기다리지 말고 끝까지 자동으로 진행한다:
- 이미 최신이면(§1-4) 아무 파일도 건드리지 말고 그대로 종료한다.
- 갱신됐다면 `git add html/ga4-channel-unsedang.html daylog/<오늘 날짜>.md` / commit
  (메시지: `"매체별 유입 리포트 자동 업데이트: <이전 창> -> <새 창>"`) / push까지 반드시
  완료한다. 저장소는 `origin/main`에 이미 연결돼 있다.
- `[SafetyError]`로 중단되면 우회 플래그 없이, 무엇이 왜 실패했는지 세션 결과에 명확히
  남기고 커밋 없이 종료한다. 신규 값 자동 분류 "경고"는 SafetyError가 아니다 — 커밋
  메시지나 daylog에 경고 내용을 그대로 남기고 정상적으로 커밋·push까지 진행한다.

## §9 보고 + daylog

1. 스크립트 출력 요약(이전 창 → 새 창, 첫 사용자 소스 그룹별 기간 합계, 전체 기간 합계,
   경고)을 사용자에게 전달한다.
2. §0의 원칙 문구를 함께 안내한다.
3. **이 커맨드는 실행할 때마다** `daylog/<오늘 날짜>.md`에 append한다:
   ```markdown
   ## <오늘 날짜> 핸드오프 — 매체별 유입 리포트 롤링 업데이트
   - 한 일: /update-ga4-channel-unsedang 실행, {이전 창} -> {새 창} 갱신
   - 변경 파일: html/ga4-channel-unsedang.html
   - 다음: 특이사항 없음 (또는 스크립트 경고 내용 요약)
   ```
   파일이 없으면 CLAUDE.md 규약대로 머리말을 붙여 새로 만든다.
