---
description: 운세당 GA4 퍼널 리포트(html/ga4-funnel-unsedang.html)를 "최근 90일" 롤링 윈도우로 매일 갱신한다(오래된 날짜는 밀려나고 최신 날짜가 추가됨). 매체별 유입 리포트와 같은 롤링형이며, 예전의 연초 누적형 방식이 아니다.
argument-hint: "[--to YYYY-MM-DD] [--dry-run]"
---

# GA4 퍼널 리포트 롤링 업데이트 (운세당)

인자: `$ARGUMENTS`

## §0 목적과 절대 원칙 (반드시 지킬 것)

**2026-09-30에 리포트 구조가 바뀌었다.** 예전에는 연초부터 날짜를 영구 누적하는
방식이었지만, 지금은 `html/ga4-channel-unsedang.html`(`/update-ga4-channel-unsedang`)과
같은 철학의 **롤링(sliding) 윈도우(최근 90일)**다. 매 실행마다:

1. 새로 확정된 날짜(들)를 `DAILY_PAGES`/`DAILY_CALL`에 추가하고
2. 윈도우 밖으로 밀려난 오래된 날짜를 제거하고(항상 90일 유지)
3. **기간 합계(`PAGE_TOTALS`, `CALL_TOTAL`)는 새 윈도우 전체를 다시 조회한 값으로
   통째로 교체**한다 — activeUsers는 비집계 지표라 오래된 값을 재사용할 수 없기 때문이다.

이 문구는 §8에서 사용자에게 그대로 전달한다.

**수집 대상(7개 페이지 + 상담하기 이벤트)**: 홈메인 · 상담사 목록 · 상담사 상세 ·
AI 상담목록 · AI 상담보기 · 운세 · 후기는 페이지 조회수 기반
(`PAGE_PATH_TO_KEY` 참고), "상담하기"는 `pre_tel_click`(선불)과 `post_tel_click`(후불) 두
이벤트를 **하나의 필터**(`eventName == 'pre_tel_click' OR eventName == 'post_tel_click'`)로
묶어 `activeUsers`를 재조회한 값(`DAILY_CALL`/`CALL_TOTAL`, 페이지와는 별개의 독립 시리즈)이다.
`eventName`을 dimension에 넣지 않아야 같은 날 두 이벤트를 모두 발생시킨 사용자가 중복
집계되지 않는다.

**이 외에 세 지표가 더 있고, 이 커맨드가 매 실행마다 함께 롤링한다**:
- **전체사용자**(`DAILY_SITE`/`SITE_ACTIVE_USERS_TOTAL`): 페이지/
  이벤트 dimension 없이 사이트 전체를 집계한 별도 시리즈.
- **AI 상담노트 트랙 이벤트**(`DAILY_SUBEVENTS`/`SUBEVENT_TOTALS`):
  `EVENT_KEYS` 7개 이벤트(`ai-note-agree-pop`, `ai-note-cancel-click`, `ai-note-agree-click`,
  `ai-note-review-skip`, `ai-note-review-next`, `ai-note-review-submit`,
  `ai-note-councel-click`) — 전부 2026-09-30부터 신규 집계된 이벤트라 그 이전 날짜는 0이
  정상이다.
- **매체별 유입**(`DAILY_FIRST_USER`/`FIRST_USER_TOTALS`):
  `GROUP_KEYS` 7개(`lg`/`notSet`/`direct`/`naverGrp`/`googleGrp`/`kakaoGrp`/`etcGrp`) —
  GA4 `firstUserSource` 원본 값을 `html/ga4-channel-unsedang.html`
  (`update_ga4_channel_unsedang.py`)과 동일한 `FIRST_USER_LABEL_TO_GROUP`/
  `classify_source()` 기준으로 그룹핑한다. firstUserSource는 사용자당 평생 하나뿐인
  값이라 단순 합산이 정확하다(병합 쿼리 불필요).

**배열 순서**: `DAILY_PAGES`의 `[a,b]` = `[활성사용자, 세션]`. `DAILY_CALL`의 `[a,b]` =
`[활성사용자, 이벤트수(eventCount)]`. `DAILY_SITE`는 `{date: 활성사용자}` (스칼라 하나).
`DAILY_SUBEVENTS`는 `{eventName: {date: 활성사용자}}` (스칼라 하나). `DAILY_FIRST_USER`의
`[a,b]` = `[활성사용자, 세션]`(그룹별).

**새 페이지 경로/이벤트/하위그룹 이벤트가 필요해지면(예: 신규 기능 추가) 이 커맨드/
스크립트만으로는 처리할 수 없다** — `scripts/update_ga4_unsedang.py`의
`PAGE_PATH_TO_KEY`/`PAGE_KEYS`/`EVENT_KEYS`와 HTML의 화면 구성 정의
(`MAIN_FUNNEL`/`AINOTE_FUNNEL`/`AINOTE_SIDE`/`PARALLEL_METRICS`/`EVENT_LABELS`)
및 `DAILY_PAGES`/`DAILY_SUBEVENTS`를 사람이 먼저 함께 갱신해야 한다. 알 수 없는 경로/eventName이 쿼리
결과에 섞여 있으면 스크립트가 `SafetyError`로 중단한다(자동 분류하지 않음 — 페이지/이벤트
목록은 고정된 소수 집합이라 조용히 넘어가면 안 된다). **단, `firstUserSource`는 다르다** —
`update-ga4-channel-unsedang`의 sessionSource처럼 새 원본 값이 나와도 `classify_source()`가
자동 분류하며 SafetyError로 중단하지 않는다(경고만 남김, §8에서 그대로 전달).

이 커맨드가 실제로 Supermetrics를 호출하는 건 여기(에이전트)뿐이다.
`scripts/update_ga4_unsedang.py`는 병합/윈도우 슬라이딩/재작성만 담당하며 MCP를
호출하지 않는다.

## §1 사전 확인

1. `get_today` 툴을 호출해 오늘 날짜를 확정한다.
2. `grep -n "const DATE_RANGE" html/ga4-funnel-unsedang.html`로 현재 창(`DATE_RANGE.from`
   ~ `DATE_RANGE.to`)을 읽는다.
3. 종료일 결정: `$ARGUMENTS`에 `--to YYYY-MM-DD`가 있으면 그 값, 없으면 **어제**
   (`new_to`, GA4 당일 데이터는 아직 불완전할 수 있음). `new_from = new_to - 89일`.
4. `incr_from = (기존 DATE_RANGE.to) + 1일`. `incr_from > new_to`이면 **"이미 최신
   상태입니다(마지막 수록일 {DATE_RANGE.to})"라고 보고하고 쿼리 없이 즉시 종료**한다.
5. `$ARGUMENTS`에 `--dry-run`이 있으면 §5에서 스크립트를 `--dry-run`으로만 실행한다.

## §2 증분 쿼리 4건 (기간: `incr_from` ~ `new_to` — 보통 하루치)

`ds_id='GAWA'`, `ds_accounts='488612198'`, `date_range_type='custom'`,
`start_date=incr_from`, `end_date=new_to`.

**쿼리 1 — 페이지 7종 (한 번에)**
- fields: `date,pagePathWithoutQueryString,activeUsers,sessions`
- filter (연산자 양쪽 공백 필수, 문자 그대로 복사):
  ```
  pagePathWithoutQueryString == '/view/home' OR pagePathWithoutQueryString == '/view/csl' OR pagePathWithoutQueryString == '/view/ai-note' OR pagePathWithoutQueryString == '/view/ai-note/noteInfo' OR pagePathWithoutQueryString == '/view/csl/cslInfo' OR pagePathWithoutQueryString == '/view/content' OR pagePathWithoutQueryString == '/view/csl/totalRatingComment'
  ```

**쿼리 2 — 상담하기(선불+후불 합산)**
- fields: `date,activeUsers,eventCount`
- filter: `eventName == 'pre_tel_click' OR eventName == 'post_tel_click'`

**쿼리 5 — 전체 활성사용자수(사이트 전체, dimension 없음)**
- fields: `date,activeUsers`
- filter: 없음

**쿼리 6 — 하위그룹 7종 (한 번에)**
- fields: `date,eventName,activeUsers`
- filter (IN-list 연산자, 문자 그대로 복사):
  ```
  eventName [] ["ai-note-agree-pop","ai-note-cancel-click","ai-note-agree-click","ai-note-review-skip","ai-note-review-next","ai-note-review-submit","ai-note-councel-click"]
  ```

**쿼리 9 — 매체별 유입(firstUserSource, 그룹핑 없는 원본)**
- fields: `date,firstUserSource,activeUsers,sessions`
- filter: 없음

응답이 비동기(`schedule_id`)면 `get_async_query_results`로 완료까지 폴링한다.

## §3 기간 전체 쿼리 4건 (비집계 지표라 필수 — 생략 금지, 기간: `new_from` ~ `new_to`)

`date_range_type='custom'`, `start_date=new_from`, `end_date=new_to`. **dimension에서
`date`를 뺀다.**

**쿼리 3 — 페이지별 기간 합계**
- fields: `pagePathWithoutQueryString,activeUsers`
- filter: 쿼리 1과 동일

**쿼리 4 — 상담하기 기간 합계**
- fields: `activeUsers,eventCount` (**dimension 없음** — 페이지/이벤트 구분 없이 이 필터에
  해당하는 값 전체)
- filter: 쿼리 2와 동일

**쿼리 7 — 전체 활성사용자수 기간 합계**
- fields: `activeUsers` (**dimension 없음**)
- filter: 없음

**쿼리 8 — 하위그룹 기간 합계**
- fields: `eventName,activeUsers` (dimension은 `eventName`만, `date` 뺌)
- filter: 쿼리 6과 동일

**쿼리 10 — 매체별 유입 기간 합계**
- fields: `firstUserSource,activeUsers` (dimension은 `firstUserSource`만, `date` 뺌)
- filter: 없음

> 왜 매번 기간 전체를 다시 물어보는가? `activeUsers`는 비집계 지표라 일별 값을 더하면
> 실제보다 부풀려진다(`docs/ga4_guide.md` §2-4). 이 리포트는 누적이 아니라 "최근 90일"
> 롤링 윈도우이므로, 창이 하루 밀릴 때마다 페이지별·상담하기·전체·하위그룹·매체별 유입
> 순사용자 수를 처음부터 다시 계산해야 정확하다.

## §4 임시 JSON 저장

`mkdir -p /tmp/ga4-funnel-update/<YYYYMMDD-HHMMSS>/` 후 아래 10개 파일을 Write:

- `pages_incremental.json`: `{"rows":[{"date","path","activeUsers","sessions"}, ...]}` (쿼리1)
- `pages_period.json`: `{"rows":[{"path","activeUsers"}, ...]}` (쿼리3)
- `call_incremental.json`: `{"rows":[{"date","activeUsers","eventCount"}, ...]}` (쿼리2)
- `call_period.json`: `{"rows":[{"activeUsers","eventCount"}]}` (쿼리4, **한 행만**)
- `site_incremental.json`: `{"rows":[{"date","activeUsers"}, ...]}` (쿼리5)
- `site_period.json`: `{"rows":[{"activeUsers"}]}` (쿼리7, **한 행만**)
- `subevents_incremental.json`: `{"rows":[{"date","eventName","activeUsers"}, ...]}` (쿼리6)
- `subevents_period.json`: `{"rows":[{"eventName","activeUsers"}, ...]}` (쿼리8)
- `firstuser_raw_incremental.json`: `{"rows":[{"date","source","activeUsers","sessions"}, ...]}` (쿼리9)
- `firstuser_raw_period.json`: `{"rows":[{"source","activeUsers"}, ...]}` (쿼리10)

`path` 필드는 `pagePathWithoutQueryString` 응답값 그대로, `eventName` 필드는 응답값
그대로(하이픈 포함, 예: `ai-note-agree-pop`) 쓴다. `source` 필드는 `firstUserSource`
응답값 그대로(예: `(not set)`, `m.search.naver.com`, `LG`) — 그룹핑은 스크립트가
`FIRST_USER_LABEL_TO_GROUP`/`classify_source()`로 처리하므로 여기서는 원본 그대로
저장한다. 값이 0이거나 GA4 응답에 없던 날짜/경로/이벤트/소스는 행을 만들지 않아도 된다
(원본도 희소 저장 방식 — 특히 "AI 상담목록"/"AI 상담보기"/하위그룹 7종은 트래픽이 매우
적어 대부분의 날짜에 행이 없는 것이 정상이다).

## §5 스크립트 실행

먼저 진단만:
```
python3 scripts/update_ga4_unsedang.py --html html/ga4-funnel-unsedang.html --indir <tmpdir> --dry-run
```
출력된 요약(새 윈도우 범위, 페이지별/상담하기/전체사용자/하위그룹/매체별 유입 기간 합계, 경고)을
확인한 뒤 `--dry-run`을 떼고 재실행한다.

`[SafetyError]`로 중단되면 **절대 우회하지 말고** 에러 메시지를 그대로 사용자에게
보고하고 원인을 파악한다 — HTML 블록을 못 찾음, 윈도우 밖 날짜 잔존, 음수 값, 신규
데이터 0건, 알 수 없는 페이지 경로(§0 참고) 등 실제 데이터 무결성 문제다.

## §6 렌더 검증 — 기본 생략

이 커맨드는 기본적으로 데이터 갱신까지만 하고 브라우저 렌더 확인은 생략한다. 사용자가
명시적으로 요청할 때만 Playwright로 확인하고, `.playwright-mcp/` 산출물은 확인 직후 삭제한다.

## §7 무인 스케줄 실행 시 (routine으로 호출된 경우)

사용자 확인을 기다리지 말고 끝까지 자동으로 진행한다:
- 이미 최신이면(§1-4) 아무 파일도 건드리지 말고 그대로 종료한다.
- 갱신됐다면 `git add html/ga4-funnel-unsedang.html daylog/<오늘 날짜>.md` / commit
  (메시지: `"GA4 퍼널 리포트 자동 업데이트: <이전 창> -> <새 창>"`) / push까지 반드시
  완료한다. 저장소는 `origin/main`에 이미 연결돼 있다.
- `[SafetyError]`로 중단되면 우회 플래그 없이, 무엇이 왜 실패했는지 세션 결과에 명확히
  남기고 커밋 없이 종료한다.

## §8 보고 + daylog

1. 스크립트 출력 요약(이전 창 → 새 창, 페이지별/상담하기/전체사용자/하위그룹/매체별 유입 기간
   합계, 경고)을 사용자에게 전달한다.
2. §0의 원칙 문구를 함께 안내한다.
3. **이 커맨드는 실행할 때마다** `daylog/<오늘 날짜>.md`에 append한다:
   ```markdown
   ## <오늘 날짜> 핸드오프 — GA4 퍼널 리포트 롤링 업데이트
   - 한 일: /update-ga4-unsedang 실행, {이전 창} -> {새 창} 갱신
   - 변경 파일: html/ga4-funnel-unsedang.html
   - 다음: 특이사항 없음 (또는 스크립트 경고 내용 요약)
   ```
   파일이 없으면 CLAUDE.md 규약대로 머리말을 붙여 새로 만든다.
