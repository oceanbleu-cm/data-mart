---
description: 운세당 GA4 퍼널 리포트(html/ga4-funnel-unsedang.html)를 마지막 수록일 이후 신규 날짜만 증분 갱신한다. 기존 데이터는 절대 재조회하지 않는다.
argument-hint: "[--to YYYY-MM-DD] [--refresh-tail N] [--dry-run]"
---

# GA4 퍼널 리포트 증분 업데이트 (운세당)

인자: `$ARGUMENTS`

## §0 목적과 절대 원칙 (반드시 지킬 것)

이 커맨드는 `html/ga4-funnel-unsedang.html`의 `DAILY_PAGES`/`DAILY_EVENTS`에 **마지막
수록일 다음 날부터의 신규 날짜만** 추가한다.

> **기존 날짜는 절대 재조회하지 않습니다.** `DAILY_PAGES`/`DAILY_EVENTS`에 이미 있는
> 날짜의 세션·이벤트수·활성사용자 값은 손대지 않고, 마지막 수록일 다음 날부터의 신규
> 날짜만 추가합니다. 딱 하나 예외가 있습니다 — `PAGE_USERS`/`EVENT_USERS`의 월별·연간
> 활성사용자는 "중복 제거된 순사용자 수"(비집계 지표)라서 날짜를 더 붙인다고 기존 값에
> 더할 수 없습니다(같은 사람이 여러 날 방문하면 이중 계산됨). 그래서 새 날짜가 걸치는
> 달과 연간 합계만 GA4에 다시 물어봅니다. 영향받지 않는 과거 달의 값은 그대로 둡니다.

이 문구는 §9에서 사용자에게 그대로 전달한다.

**배열 순서 — 절대 헷갈리지 말 것**: `DAILY_PAGES`의 `[a,b]` = `[활성사용자, 세션]`.
`DAILY_EVENTS`의 `[a,b]` = `[활성사용자, 이벤트수]`. 둘 다 index 0이 활성사용자다
(화면 표시 순서는 반대라서 헷갈리기 쉽다).

이 커맨드가 실제로 Supermetrics를 호출하는 건 여기(에이전트)뿐이다.
`scripts/update_ga4_unsedang.py`는 병합/재작성만 담당하며 MCP를 호출하지 않는다.

---

## §1 사전 확인

1. `get_today` 툴을 호출해 오늘 날짜를 확정한다(상대 날짜 계산 전 필수).
2. `grep -n "const DATE_RANGE\|const MONTHS" html/ga4-funnel-unsedang.html`로 현재
   마지막 수록일(`DATE_RANGE.to`)과 `MONTHS` 배열을 읽는다.
3. 종료일 결정: `$ARGUMENTS`에 `--to YYYY-MM-DD`가 있으면 그 값, 없으면 **어제**
   (GA4 당일 데이터는 아직 불완전할 수 있음).
4. `new_from = (기존 DATE_RANGE.to) + 1일`. `new_from > new_to`이면 **"이미 최신
   상태입니다(마지막 수록일 {DATE_RANGE.to})"라고 보고하고 쿼리 없이 즉시 종료**한다.
5. `new_from`의 연도가 `DATE_RANGE.from`의 연도와 다르면 중단하고 사용자에게 보고한다
   (연도 경계를 넘는 갱신은 이 리포트 구조에서 지원하지 않음 — 탭 라벨/연간 집계
   재설계가 먼저 필요).
6. `$ARGUMENTS`에 `--dry-run`이 있으면 §7에서 스크립트를 `--dry-run`으로만 실행한다.

## §2 일별 쿼리 5건

`ds_id='GAWA'`, `ds_accounts='488612198'`, `date_range_type='custom'`,
`start_date=new_from`, `end_date=new_to`로 아래 5개 쿼리를 실행한다.

**쿼리 1 — 페이지 9종 (한 번에)**
- fields: `date,pagePathWithoutQueryString,activeUsers,sessions`
- filter (연산자 양쪽 공백 필수, 문자 그대로 복사):
  ```
  pagePathWithoutQueryString == '/view/home' OR pagePathWithoutQueryString == '/view/csl' OR pagePathWithoutQueryString == '/view/csl/cslInfo' OR pagePathWithoutQueryString == '/view/free' OR pagePathWithoutQueryString == '/view/free/registrationStart' OR pagePathWithoutQueryString == '/view/free/registrationForm' OR pagePathWithoutQueryString == '/view/free/registrationEnd' OR pagePathWithoutQueryString == '/view/content' OR pagePathWithoutQueryString == '/view/fortune/unseYear'
  ```

**쿼리 2 — 후불상담(postTel)**
- fields: `date,activeUsers,eventCount`
- filter: `eventName =@ 'post_tel_click' AND pagePathWithoutQueryString == '/view/csl/cslInfo'`

**쿼리 3 — 선불상담(preTel)**
- fields: `date,activeUsers,eventCount`
- filter: `eventName =@ 'pre_tel_click' AND pagePathWithoutQueryString == '/view/csl/cslInfo'`

**쿼리 4 — 홈 상담사 클릭(coachMark)**
- fields: `date,activeUsers,eventCount`
- filter: `eventName == 'coach_mark_main_click' AND pagePathWithoutQueryString == '/view/home'`

**쿼리 5 — 홈 배너 클릭(banner)**
- fields: `date,activeUsers,eventCount`
- filter: `eventName == 'main_banner_click' AND pagePathWithoutQueryString == '/view/home'`

⚠️ **쿼리 2의 필터를 `/view/home`까지 포함하도록 바꾸지 말 것.** `docs/ga4_guide.md` §4에
따르면 `post_tel_click`은 `/view/home`에서도 발생하지만, 이 리포트는 처음부터
`/view/csl/cslInfo`로만 필터링해 시계열을 쌓아왔다. 필터를 바꾸면 과거 데이터와
단절되어 전체 시계열이 깨진다.

응답이 비동기(`schedule_id`)면 `get_async_query_results`로 완료까지 폴링한다.
`eventName =@`는 `_mobile`/`_pc`/`_res_false` 변형을 모두 포함하기 위한 것이므로
`eventName`을 dimension에 넣지 않는다(넣으면 변형별로 쪼개져 활성사용자 dedup이 깨짐).

## §3 영향받는 달 판별

```
affected_months = { d[:7] for d in (new_from ~ new_to 사이의 모든 날짜) }
```
쿼리 결과에 실제로 나온 날짜들의 연-월을 그대로 집합으로 만들면 된다. 별도 로직 불필요
— 이전 `MONTHS`의 마지막 달은 신규 날짜가 실제로 그 달에 걸칠 때만 자동으로 포함된다.

## §4 월별 재조회 5건 (비집계 지표라 필수 — 생략 금지)

`date_range_type='custom'`, `start_date = affected_months 중 가장 이른 달의 1일`,
`end_date = new_to`. metric은 **`activeUsers`만**(세션/이벤트수는 일별 합산으로 충분).

- 페이지: fields `yearMonth,pagePathWithoutQueryString,activeUsers`, filter = §2 쿼리1과 동일
- postTel/preTel/coachMark/banner: fields `yearMonth,activeUsers`, filter = §2의 각 필터와 동일

## §5 연간 재조회 5건 (비집계 지표라 필수 — 생략 금지)

`date_range_type='custom'`, `start_date='2026-01-01'`(=`DATE_RANGE.from`), `end_date=new_to`.

- 페이지: fields `pagePathWithoutQueryString,activeUsers`, filter = §2 쿼리1과 동일
- postTel/preTel/coachMark/banner: fields `activeUsers` (**dimension 없음**), filter = §2의 각 필터와 동일

> 왜 dimension 없이? `activeUsers`는 비집계 지표라 월별 값을 사람이 더하면 실제보다
> 부풀려진다(`docs/ga4_guide.md` §2-4). 페이지에 `pagePathWithoutQueryString`만 남기는
> 건 경로별로 독립된 dedup 값을 한 번에 받기 위함이며, 이 결과를 서로 더하지 않는다.

## §6 임시 JSON 저장

`mkdir -p /tmp/ga4-funnel-update/<YYYYMMDD-HHMMSS>/` 후 아래 4개 파일을 Write:

- `daily_pages.json`: `{"rows":[{"date","path","activeUsers","sessions"}, ...]}` (§2 쿼리1 결과)
- `daily_events.json`: `{"rows":[{"event","date","activeUsers","eventCount"}, ...]}`
  (`event` ∈ `preTel`|`postTel`|`coachMark`|`banner`, §2 쿼리2~5 결과를 이 스키마로 합쳐서 저장)
- `users_monthly.json`: `{"pages":[{"yearMonth","path","activeUsers"}, ...], "events":[{"yearMonth","event","activeUsers"}, ...]}` (§4 결과, `yearMonth`는 `2026-09`든 `2026|09`든 상관없음)
- `users_yearly.json`: `{"pages":[{"path","activeUsers"}, ...], "events":[{"event","activeUsers"}, ...]}` (§5 결과, **13개 시리즈 전부 포함 필수**)

값이 0이거나 GA4 응답에 아예 없던 날짜/이벤트는 행을 만들지 않는다(원본도 희소 저장 방식).

## §7 스크립트 실행

먼저 진단만:
```
python3 scripts/update_ga4_unsedang.py --html html/ga4-funnel-unsedang.html --indir <tmpdir> --dry-run
```
출력된 요약(추가된 날짜 수, 재조회 반영 범위, 경고)을 확인한 뒤 `--dry-run`을 떼고 재실행한다.

`[SafetyError]`로 중단되면 **절대 우회 플래그를 임의로 붙이지 말고** 에러 메시지를
그대로 사용자에게 보고하고 원인을 파악한다(오타·범위 오류·비집계 지표 검증 실패 등).

`$ARGUMENTS`에 `--refresh-tail N`이 있으면 §10을 따른다.

## §8 렌더 검증 — 기본 생략

이 커맨드는 기본적으로 데이터 갱신까지만 하고 브라우저 렌더 확인은 생략한다(빠른 반복
실행을 위해). 사용자가 명시적으로 요청할 때만 Playwright로 `html/ga4-funnel-unsedang.html`을
열어 최신 월 탭에 신규 날짜가 보이는지 확인하고, `.playwright-mcp/` 산출물은 확인 직후
삭제한다.

## §9 보고 + daylog

1. 스크립트 출력 요약(기간 변화, 추가된 키 개수, 재조회 반영 범위, 미변경 범위, 경고)을
   사용자에게 전달한다.
2. §0의 원칙 문구를 함께 안내한다(특히 이번에 어떤 달이 재조회됐는지, 왜인지).
3. **이 커맨드는 실행할 때마다** `daylog/<오늘 날짜>.md`에 append한다(CLAUDE.md의
   "세션 종료 시 1회"보다 좁혀, 매 실행마다 기록하도록 명시적으로 지시받았다):
   ```markdown
   ## <오늘 날짜> 핸드오프 — GA4 퍼널 증분 업데이트
   - 한 일: /update-ga4-unsedang 실행, {이전 to} ~ {새 to} 신규 반영 (일별 +N개, 재조회 월 {affected_months})
   - 변경 파일: html/ga4-funnel-unsedang.html
   - 다음: 특이사항 없음 (또는 스크립트 경고 내용 요약)
   ```
   파일이 없으면 CLAUDE.md 규약대로 머리말을 붙여 새로 만든다.

## §10 `--refresh-tail N` (옵션, 기본 꺼짐)

GA4 최근 1~2일 데이터는 처리 지연으로 확정되지 않을 수 있다. 사용자가 `$ARGUMENTS`에
`--refresh-tail N`을 명시했을 때만: 기존 마지막 N일도 §2~§5 쿼리 범위에 포함시키고,
§7에서 스크립트에 `--allow-tail-overwrite`를 추가로 전달한다. 기본은 꺼져 있다 —
"기존 데이터 재조회 금지" 원칙을 지키기 위함이다.
