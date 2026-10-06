---
description: 네이버 파워링크(광고) 유입→화면이동→상담신청 퍼널을 사용자가 지정한 기간으로 새로 집계해 html/ga4-naver-powerlink-unsedang.html과 같은 구조의 리포트를 "새 파일"로 만든다. 롤링 갱신이 아니라 기간별 스냅샷이며, 기존 파일은 절대 덮어쓰지 않는다.
argument-hint: "[--from YYYY-MM-DD --to YYYY-MM-DD]"
---

# 네이버 파워링크 퍼널 리포트 생성 (운세당)

인자: `$ARGUMENTS`

## §0 목적과 절대 원칙 (반드시 지킬 것)

이 커맨드는 `html/ga4-naver-powerlink-unsedang.html`(최초 스냅샷, 2026-10-02~10-05 고정)과
**동일한 구조·스타일·용어(비전문가용 plain 언어)**로, 사용자가 매번 지정하는 **임의의 기간**에
대한 새 스냅샷을 만든다.

- **롤링 윈도우 아니다.** `/update-ga4-unsedang`과 달리 과거 파일을 갱신하지 않고, 실행마다
  **새 파일을 추가**한다. 기존 산출물(날짜 없는 원본 포함)은 절대 덮어쓰거나 삭제하지 않는다.
- **이 커맨드는 프로젝트 전용**이다(`.claude/commands/`에만 존재, 전역 커맨드 아님).
- 매 실행마다 BigQuery로 **그 기간을 처음부터 다시 실측**한다 — 다른 기간의 결과(광고 코드
  목록, 효율 등급, 후불 직접전환 비율 등)를 재사용하거나 가정하지 않는다. 광고 코드 구성이나
  전환 패턴은 기간마다 달라질 수 있다.
- site-nav는 이 커맨드가 자동으로 건드리지 않는다(어느 스냅샷을 nav에 노출할지는 사용자가
  별도로 지시할 사항).
- git push는 하지 않는다(리더 지시 시에만) — [[feedback-no-auto-deploy]] 참고.

## §1 조회 기간 확인

1. `$ARGUMENTS`에 `--from YYYY-MM-DD --to YYYY-MM-DD`가 모두 있으면 그 값을 쓴다.
2. 없으면 **사용자에게 직접 질문**한다: "조회 시작일과 종료일을 알려주세요 (예: 2026-10-06 ~
   2026-10-12)." — 추측하거나 기본값을 임의로 정하지 않는다.
3. `get_today` 툴로 오늘 날짜를 확인하고 다음을 검증, 위반 시 사용자에게 알리고 재확인받는다:
   - `종료일 <= 어제` (GA4 당일 데이터는 집계가 불완전할 수 있음)
   - `시작일 <= 종료일`
   - `시작일 >= 2026-08-26` 전후(GA4 BigQuery export 시작일 — [[reference-bigquery-ga4-export]]
     참고, 그 이전 날짜는 `events_YYYYMMDD` 테이블 자체가 없을 수 있음)

## §2 BigQuery 접속 정보

- `projectId: "unsedang"`, `datasetId: "analytics_488612198"` ([[reference-bigquery-ga4-export]]
  — GA4/Supermetrics 계정명인 `unsedang-a3588`과 다르니 혼동하지 말 것).
- 테이블: `events_*` 와일드카드에 `_TABLE_SUFFIX BETWEEN 'YYYYMMDD' AND 'YYYYMMDD'`로 기간을
  제한(또는 `events_YYYYMMDD`를 날짜별로 UNION ALL). 쿼리 전, 해당 기간의 모든 날짜에 대해
  테이블이 실제로 존재하는지 `list_table_ids`/`get_table_info`로 먼저 확인하고, 없는 날짜가
  있으면 사용자에게 알린다(과거처럼 조용히 빈 결과로 넘기지 않는다).

## §3 세션 기준 테이블 구성 (SQL 스켈레톤)

표준 GA4 export 스키마 기준. `ga_session_id`는 `event_params`(key='ga_session_id')의
`value.int_value`, `page_location`은 `event_params`(key='page_location')의
`value.string_value`(전체 URL이므로 path만 추출해 써야 함 — REGEXP_EXTRACT로 `https?://[^/]+`
제거).

```sql
WITH base AS (
  SELECT
    user_pseudo_id,
    (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id') AS session_id,
    event_name,
    event_timestamp,
    (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location') AS page_location,
    collected_traffic_source.manual_source AS manual_source,
    collected_traffic_source.manual_medium AS manual_medium,
    collected_traffic_source.manual_term AS manual_term
  FROM `unsedang.analytics_488612198.events_*`
  WHERE _TABLE_SUFFIX BETWEEN '<YYYYMMDD_from>' AND '<YYYYMMDD_to>'
),
session_attrib AS (
  SELECT
    user_pseudo_id, session_id,
    ARRAY_AGG(manual_source IGNORE NULLS LIMIT 1)[SAFE_OFFSET(0)] AS source,
    ARRAY_AGG(manual_medium IGNORE NULLS LIMIT 1)[SAFE_OFFSET(0)] AS medium,
    ARRAY_AGG(manual_term  IGNORE NULLS LIMIT 1)[SAFE_OFFSET(0)] AS term
  FROM base GROUP BY 1, 2
),
powerlink_sessions AS (
  -- source='naver' + medium이 숫자 코드 형태(정규식) — 코드 목록을 하드코딩하지 않고
  -- 그 기간에 실제로 관측된 값으로 매번 다시 산출한다(기간마다 코드가 바뀔 수 있음).
  SELECT * FROM session_attrib
  WHERE source = 'naver' AND REGEXP_CONTAINS(medium, r'^[0-9]{2,4}$')
)
```

이 `powerlink_sessions`가 0건이면 "해당 기간 네이버 파워링크 유입 없음"으로 바로 보고하고
종료한다(리포트를 만들지 않는다).

## §4 화면 이동 순서 (퍼널 단계 판정)

`event_name = 'page_view'` 행만 써서 `page_location`에서 path를 뽑고, 아래 7개 키로 분류한다
(`scripts/update_ga4_unsedang.py`의 `PAGE_PATH_TO_KEY`와 동일 — 이 리포트에선 그중 `home`,
`totalRatingComment`(후기), `cslInfo`(상담사 소개)만 핵심 퍼널에 쓰고, `csl`(목록)은 §0 원칙상
퍼널 중간 단계로 넣지 않는다 — 목록 미경유 직접 진입이 많아 비율이 100%를 넘기 때문. 단, 숫자
자체는 참고용으로 같이 뽑아둔다):

```
/view/home                      -> home
/view/csl                       -> csl (참고용, 핵심 퍼널 제외)
/view/csl/cslInfo               -> cslInfo (상담사 소개)
/view/csl/totalRatingComment    -> totalRatingComment (후기)
/view/ai-note                   -> aiNote
/view/ai-note/noteInfo          -> aiNoteInfo
/view/content                   -> content (운세)
```

세션별로 `MAX(CASE WHEN path_key = 'totalRatingComment' THEN 1 ELSE 0 END)` 식으로 각 단계
도달 여부 플래그를 만든다. **알 수 없는 path가 상당수 섞여 있으면(오탈자/신규 화면 추가 가능성)
무시하지 말고 사용자에게 보고한다** — 위 매핑 외 경로가 유의미한 비중(예: 전체의 1% 이상)이면
새 화면이 생겼을 가능성이 있다.

## §5 상담 신청 이벤트와 "직접전환" 판정

- `event_name IN ('pre_tel_click', 'post_tel_click')` 행을 뽑아 세션 단위로 dedup(같은 세션에서
  같은 이벤트가 여러 번 찍혀도 1건으로 — 기존 리포트와 동일 기준).
- **클릭 이벤트 자체의 `page_location`은 쓰지 않는다** — SPA 라우팅 특성상 신뢰 불가(과거
  사례: post_tel_click의 90% 이상이 `/view/home`으로 고정 기록됨). 대신 같은 세션 내에서
  `event_timestamp < 클릭 시각`인 `page_view` 행 중 **가장 늦은 것**을 "클릭 직전 마지막 화면"으로
  판정한다(윈도우 함수 또는 상관 서브쿼리로 `ORDER BY event_timestamp DESC LIMIT 1`).
- "상담사 소개 화면을 거치지 않고 신청"(직접전환) = 클릭 이전 해당 세션에 `cslInfo` 도달 플래그가
  0인 경우. 이 비율과, 직접전환 세션들의 "클릭 직전 마지막 화면" 상위 분포(이전 기간엔 `/view/home`
  20건, `/view/qa` 2건이었음 — **이번 기간에도 같을 거라 가정하지 말고 매번 다시 집계**한다)를
  둘 다 구한다.
- 선불/후불 각각의 건수, 그리고 "둘 중 하나라도 신청"(OR, 세션 기준 중복제거) 합계를 구한다.

## §6 키워드 랭킹

- `manual_term`이 `(not set)` / 빈 문자열 / 리터럴 문자열 `{keyword}`(네이버 동적 키워드 삽입
  실패 추정치)인 세션은 랭킹에서 제외하고, 제외 건수를 note에 남긴다(기존 리포트의 "68건 제외"
  문구와 같은 역할).
- 남은 키워드별로 **방문**(session 수), **방문자**(`COUNT(DISTINCT user_pseudo_id)`),
  **선불신청/후불신청/신청합계**(§5의 세션별 플래그를 키워드로 group by)를 전부 BigQuery
  한 번으로 집계한다(기존처럼 Supermetrics와 BigQuery를 따로 돌려 수기 병합하지 않는다 —
  BigQuery 안에서 sessions/users/conversions를 한꺼번에 뽑으면 두 도구 간 1~2건 오차 문제
  자체가 생기지 않는다). 방문수 내림차순으로 순위를 매긴다.
- (선택, 교차검증용) Supermetrics(`ds_id='GAWA'`, `account='488612198'`)로 같은 기간
  `sessionSource==naver` 단일조건 세션 합계를 한 번 더 조회해 BigQuery 총 세션수와 비교해도
  된다 — 단, Supermetrics 필터 DSL은 **`AND` 뒤에 `OR` 묶음이나 IN-list를 쓰면 조용히 빈
  결과를 낸다**(이번 세션에서 실제로 겪은 버그)는 점을 기억하고, 반드시 단일 `==` 조건으로만
  쓴다.

## §7 집계 → 표/카드 내용 구성

기존 리포트의 섹션 구조를 그대로 따른다:
1. 한눈에 보기(TL;DR 4개 불릿)
2. 어떻게 확인했나(요약 2~3문장, 기술 디테일은 footer `<details>`로)
3. 요약 숫자(kpi-tile 6개: 유입/후기열람/소개열람/선불/후불/합계중복제거)
4. 상담 신청까지 가는 흐름(fnl-row/fnl-conn 3단계 + 선불·후불 분기 mini-grid + 직접전환 경고 note)
5. 광고 코드별 성과표(§3에서 실제 관측된 코드 전부, 기존 코드 개수와 다를 수 있음 — 효율 태그:
   방문 대비 신청률 10%+ 좋음/5~10% 보통/5%미만 낮음/0건 전환없음, 방문 30 미만이면 `*`)
6. 들어온 검색어 전체 순위(§6 표 전체, 방문/방문자/선불신청/후불신청/신청합계 열 + 클릭 정렬
   JS — 기존 `#kwTable` 스크립트를 그대로 재사용)
7. footer: 이번 기간 조회일, 데이터 출처(전부 BigQuery라고 명시, 하이브리드였던 이전 버전과
   다름), 세션 식별 방법 요약

## §8 파일 생성 & 버전 관리 (덮어쓰기 금지)

1. `get_today`로 **요청일**(명령 실행일, 조회 기간과는 다른 개념)을 확인한다.
2. 기본 파일명: `html/ga4-naver-powerlink-unsedang-<요청일>.html`
3. 이미 그 이름의 파일이 있으면 `-v1`을 붙이고, 그것도 있으면 `-v2`, ... 식으로 **비어있는
   이름을 찾을 때까지 증가**시킨다. 즉 같은 날 여러 번 실행해도 서로 다른 파일로 쌓인다.
4. 날짜 없는 원본 `html/ga4-naver-powerlink-unsedang.html`은 **절대 건드리지 않는다**
   (최초 스냅샷, 과거 산출물로 그대로 보존).
5. 새 파일은 Write 전용(해당 경로는 신규 파일이라 Read 선행 조건 없음) — CSS/스크립트 블록은
   기존 파일에서 그대로 복사하고, 본문 텍스트·표·수치만 이번 기간 값으로 교체한다.

## §9 검증

- 광고 코드별 표의 방문/신청 합계가 §3·§5에서 구한 전체 합계와 일치하는지 확인.
- 키워드 표의 신청합계가 요약 KPI의 전환합계(중복제거)보다 작거나 같은지 확인(차이는
  "검색어 미기록 세션" 때문 — note에 그 차이값을 적는다).
- 순위 번호가 1부터 연속이고 중복이 없는지 기계적으로 확인(Python/grep 등).
- Playwright 렌더 확인은 기본 생략, 사용자가 명시적으로 요청할 때만 수행하고 `.playwright-mcp/`
  산출물은 즉시 삭제한다.

## §10 보고 + daylog

1. 사용자에게 조회 기간, 생성된 파일 경로, 핵심 KPI(유입/전환합계/가장 빠지는 구간/코드별
   특이사항)를 간결히 보고한다.
2. `daylog/<오늘 날짜>.md`에 append(CLAUDE.md 규약, 머리말 없으면 새로 생성):
   ```markdown
   ## <오늘 날짜> 핸드오프 — 네이버 파워링크 퍼널 리포트 신규 생성 (/naver-powerlink)
   - 한 일: <조회 시작일>~<조회 종료일> 기간으로 새 스냅샷 생성
   - 변경 파일: html/ga4-naver-powerlink-unsedang-<요청일>[-vN].html (신규)
   - 다음: 특이사항 없음 (또는 발견한 이상치 요약)
   ```
3. git push는 하지 않음(리더 지시 시에만).
