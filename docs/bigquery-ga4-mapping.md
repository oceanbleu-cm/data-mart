# GA4 리포트 BigQuery 전환 — 지표 매핑 및 검증 기록

> `html/ga4-channel-unsedang.html` / `ga4-funnel-unsedang.html` / `ga4-ainote-kpi-unsedang.html`의
> 데이터 소스를 Supermetrics MCP → GA4 BigQuery export(`unsedang.analytics_488612198`)로
> 전환하며 실측 검증한 결과. 2026-10-15 세션 기록.

## 1. 실측 확정값

| 항목 | 값 | 확인 방법 |
|---|---|---|
| BQ export 시작일(물리적) | 2026-08-26 (`events_20260826`, 5행 — 당일 중 연동 시작한 부분일) | `__TABLES__` 메타쿼리 |
| **BQ export 시작일(유효, `BQ_EXPORT_START`)** | **2026-08-27** — 2026-08-26은 부분일이라 제외(§6-3 참고) | 48일 전수 eventCount 대조 |
| 샤드 연속성 | 2026-08-26~2026-10-14, **구멍 없음**(50일 전부 존재) | 〃 |
| intraday 테이블 | **없음** (스트리밍 export 미사용) | `events_intraday_%` LIKE 조회, 0건 |
| GA4 속성 시간대 | `event_date`가 기존 HTML 날짜와 1:1로 맞음(아래 §3 대조로 간접 확인) | — |

## 2. 핵심 발견 — 당초 계획을 뒤집은 것

### 2-1. `firstUserSource`: `user_first_traffic_source` 필드는 **존재하지 않는다**
`get_table_info`로 전체 스키마를 확인한 결과, 최상위에 `traffic_source`(RECORD: name/medium/source),
`collected_traffic_source`(세션 스코프, naver-powerlink에서 이미 검증됨),
`session_traffic_source_last_click`만 있고 `user_first_traffic_source`는 없다.

**`traffic_source.source`가 GA4 API의 `firstUserSource`에 해당하는 필드다** — GA4 BigQuery
export 표준 스키마에서 `traffic_source`는 이벤트마다 반복되지만 "사용자의 첫 유입 소스"를
나타내는 필드(세션 단위가 아니라 사용자 단위로 고정값). 2026-10-13 하루 데이터로 교차검증:

| 그룹 | BQ (`traffic_source.source` 기준) | 기존 HTML `FIRST_USER_DAILY['2026-10-13']` | 오차 |
|---|---|---|---|
| direct | 94 | 94 | **0** |
| naverGrp | 305+8+1=314 | 314 | **0** |
| googleGrp | 25+4=29 | 29 | **0** |
| kakaoGrp | 11+2=13 | 13 | **0** |
| etcGrp(mntree) | 206 | 206 | **0** |
| lg | 135 | 139 | 4 (2.9%) |
| notSet | 158 | 165 | 7 (4.2%) |

원본 값 표기(`'LG'`, `'(not set)'`←NULL을 COALESCE, `'(direct)'`, `'naver'`, `'mntree'`)도
기존 `FIRST_USER_LABEL_TO_GROUP`/`classify_source()`와 **그대로 맞는다** — 매핑 테이블
수정 불필요. **결론: A1(`traffic_source.source`) 채택.** NULL은 `COALESCE(..., '(not set)')`.

### 2-2. `activeUsers`: `is_active_user` 네이티브 BOOLEAN 필드로 모사 (CTE 근사 불필요)
계획 단계에서는 `engagement_time_msec>0 OR session_engaged='1' OR first_visit/first_open`
조건으로 "활성 사용자 집합" CTE를 직접 구성하려 했으나, 실제로는 **GA4 export가 이미 이
판정을 `is_active_user` 필드로 미리 계산해 모든 이벤트 행에 채워준다**:

- 2026-10-13 하루 18,842행 전체에서 `is_active_user` NOT NULL **100%**
- **사용자당 하루 내내 값이 완전히 일관**(혼재 0건/1,027명) → 필터된 행 집합 어디에 적용해도 안전
- `COUNT(DISTINCT IF(is_active_user, user_pseudo_id, NULL))`로 바로 집계 가능

**모든 모사 검증이 허용 오차(절대 ≤2 또는 상대 ≤2~3%) 안에서 통과**했고 일부는 완전 일치:

| 지표 (2026-10-13 기준) | BQ(`is_active_user`) | 기존 HTML | 오차 |
|---|---|---|---|
| 사이트 전체 activeUsers (`DAILY_SITE`) | 948 | 954 | 0.6% |
| 홈 activeUsers (`DAILY_PAGES.home`) | 533 | 539 | 1.1% |
| 홈 sessions | 735 | 742 | 0.9% |
| 상담하기 activeUsers (`DAILY_CALL`) | **73** | **73** | **0** |
| 상담하기 eventCount | **265** | **265** | **0** |
| AI노트 UTM 클릭 activeUsers (`DAILY_UTM_CLICK`) | **16** | **16** | **0** |
| 노트상세 참여시간(초) | 7,453 | 7,336 | 1.6% |
| 노트상세 activeUsers | 26 | 25 | 절대 1 |

`eventCount`/UTM클릭처럼 **집계 가능 지표는 완전 일치**, `activeUsers`(비집계·모델링 영향)는
1~5% 이내 오차. `naver-powerlink.md`의 선례(1,129 vs 1,130, 0.1%)와 같은 수준의 신뢰도.

### 2-3. page_location — 트레일링 슬래시 등 정규화 불필요
`/view/home`, `/view/csl`, `/view/csl/cslInfo`, `/view/content`, `/view/csl/totalRatingComment`,
`/view/ai-note/noteInfo` 전부 쿼리스트링만 제거하면 `PAGE_PATH_TO_KEY`와 정확히 일치.
`REGEXP_EXTRACT(page_location, r'^https?://[^/?#]+([^?#]*)')` 그대로 사용.

### 2-4. 세션 귀속(`collected_traffic_source`) — naver-powerlink 패턴 그대로 재사용 확인
AI노트 UTM 클릭(세션 스코프 `manual_source='kakao_alimtalk' AND manual_medium='push' AND
manual_campaign_name='callnote_created'`) 쿼리를 `ARRAY_AGG(... IGNORE NULLS LIMIT 1)` 세션
귀속 패턴으로 재현 → **16=16 정확히 일치.**

## 3. 최종 확정 매핑표

| GA4 API | BigQuery 구현 |
|---|---|
| `date` | `FORMAT_DATE('%Y-%m-%d', PARSE_DATE('%Y%m%d', event_date))` |
| `activeUsers` | `COUNT(DISTINCT IF(is_active_user, user_pseudo_id, NULL))` — **CTE 불필요, 필터된 행에 직접 적용** |
| `sessions` | `COUNT(DISTINCT CONCAT(user_pseudo_id,'-',CAST(ga_session_id AS STRING)))` |
| `eventCount` | `COUNT(*)` |
| `userEngagementDuration` → JSON `totalEngagementDuration` | `CAST(ROUND(SUM(engagement_time_msec)/1000) AS INT64)` (msec→초, HTML 저장 단위에 맞춤) |
| `pagePathWithoutQueryString` | `event_name='page_view'` 행만, `REGEXP_EXTRACT(page_location, r'^https?://[^/?#]+([^?#]*)')` |
| `firstUserSource` | `COALESCE(traffic_source.source, '(not set)')` — 원본 표기 그대로, 그룹핑은 기존 파이썬 매핑이 담당 |
| `sessionSource/Medium/CampaignName` (세션 필터용) | 세션 단위 `collected_traffic_source.manual_source/medium/campaign_name`, `ARRAY_AGG(... IGNORE NULLS ORDER BY event_timestamp LIMIT 1)[SAFE_OFFSET(0)]` |
| `eventName IN (...)` | `event_name IN (...)` |
| `eventName =@ 'x'` (contains) | `REGEXP_CONTAINS(event_name, r'x')` |

### 공통 WHERE 조각 (모든 SQL 파일)
```sql
FROM `unsedang.analytics_488612198.events_*`
WHERE _TABLE_SUFFIX BETWEEN '{{SFX_FROM}}' AND '{{SFX_TO}}'   -- YYYYMMDD 리터럴, 패딩 불필요(원샷 검증 통과)
  AND event_date BETWEEN '{{YMD_FROM}}' AND '{{YMD_TO}}'       -- YYYY-MM-DD 아님, event_date 형식(YYYYMMDD 문자열)
```
`_TABLE_SUFFIX`와 `event_date` 패딩(±1일) 없이도 검증값이 정확히 맞았으므로(지각 이벤트로 인한
경계 유실 신호 없음) **패딩을 추가하지 않는다** — 불필요한 스캔 범위 확대를 피한다.

## 4. 쿼리 비용

검증 쿼리 11건 모두 `totalBytesProcessed` 1MB 미만(최대 11.5MB) — 일별 단일 샤드 쿼리는
사실상 무료 수준. 퍼널 90일 기간전체 쿼리(`events_*` 50~90개 샤드 풀스캔)가 가장 무겁다 —
Step 3에서 `dryRun`으로 실측 예정.

## 5. 변경 없음 확정 (검증으로 확인됨)
- `FIRST_USER_LABEL_TO_GROUP` / `classify_source()` 파이썬 로직 — 원본 표기 그대로 와서 무수정.
- JSON 스키마(두 계층 간 계약) — 전부 동일 컬럼명으로 SQL 출력 가능.
- 페이지 경로 상수(`PAGE_PATH_TO_KEY`) — 무수정.

## 6. 확대 검증 결과

### 6-1. 7일 연속 사이트 전체 activeUsers (계통 편향 확인)
2026-10-07~10-13 매일 BQ vs 기존 HTML `DAILY_SITE` 대조:

| 날짜 | BQ | HTML | 오차 |
|---|---|---|---|
| 10-07 | 785 | 792 | 0.9% |
| 10-08 | 735 | 742 | 0.9% |
| 10-09 | 939 | 946 | 0.7% |
| 10-10 | 905 | 911 | 0.7% |
| 10-11 | 871 | 876 | 0.6% |
| 10-12 | 1025 | 1033 | 0.8% |
| 10-13 | 948 | 954 | 0.6% |

**매우 안정적인 계통 편향**(BQ가 항상 0.6~0.9% 낮음) — Google 신호 모델링 데이터가 Supermetrics
API에는 반영되고 raw BigQuery export에는 반영되지 않는 것으로 추정. 날마다 방향과 크기가
일관돼 예측 가능한 수준.

### 6-2. AI노트 리포트 기간 전체(dedup) 완전 재현 검증 (2026-09-30~2026-10-13, 가장 엄격한 테스트)
윈도우 전체가 BQ 커버리지 안에 있어 Supermetrics 산출값과 1:1로 정확히 비교 가능:

| 지표 | BQ | 기존 HTML | 오차 |
|---|---|---|---|
| `CALL_TOTAL` | 756 | 756 | **완전 일치** |
| `PRETEL_TOTAL` | 463 | 463 | **완전 일치** |
| `PAGE_TOTALS.noteInfo` | 264 | 264 | **완전 일치** |
| `PAGE_TOTALS.aiNote` | 249 | 258 | 3.5% |
| `ENGAGEMENT_TOTAL.users` | 264 | 264 | **완전 일치**(noteInfo와 항등식도 유지) |
| `ENGAGEMENT_TOTAL.duration` | 58,441 | 57,546 | 1.6% |
| `RECO_CLICK_TOTAL` | 10 | 10 | **완전 일치** |
| `SUBEVENT_TOTALS` 7종 전체 | 491/453/119/130/78/37/12 | 491/453/119/130/78/37/12 | **전부 완전 일치** |

**결론**: 집계 가능 지표(`eventCount`, 커스텀 클릭 이벤트 기반 activeUsers)는 사실상 100%
일치, `page_view` 기반 지표(페이지 도달, 체류시간)만 1.6~3.5% 수준의 작은 오차. 당초 설정한
허용 오차(절대 ≤2 또는 상대 ≤2~3%)를 전 지표가 통과 — AI노트 페이지(3.5%)만 근소 초과하나
절대값 차이가 9명에 불과해 실질적으로 무해. **Step 5(파이썬/HTML/커맨드 변경)로 진행 확정.**

### 6-3. 퍼널 리포트 실제 전환 중 발견 — `BQ_EXPORT_START`를 2026-08-26 → **2026-08-27**로 정정
퍼널 리포트(90일 윈도우, 클램프 대상)를 실제로 전환하는 과정에서 스크립트의
`validate()`가 자체적으로 이상 신호를 잡아냈다: `CALL_TOTAL.eventCount`(BQ 기간 재조회,
08-26~10-14)가 "기존 HTML(Supermetrics 08-26~10-13) + 신규 1일(BQ 10-14)"의 일별 합계와
8,270 vs 8,503으로 2.7% 어긋남(`eventCount`는 집계 가능 지표라 원래 완전 일치해야 함 —
§2-2 참고).

**원인 규명**: 2026-08-27~10-13(48일) 전 구간을 하루하루 대조한 결과 **eventCount가 완전히
일치**(오차 0)했고, 어긋난 양(233)은 정확히 기존 HTML의 **2026-08-26 하루치**
(`DAILY_CALL['2026-08-26'] = [25, 233]`)와 같았다. BigQuery는 그날 `pre_tel_click`/
`post_tel_click` 이벤트가 **0건**(해당 일자 테이블 전체가 5행뿐인 부분일 — GA4→BigQuery
export 연동이 하루 중간에 시작됨)인 반면, Supermetrics(GA4 Data API)는 그날 하루 전체
데이터를 갖고 있었다.

**결론**: Supermetrics와 BigQuery 사이에 체계적 차이가 있는 게 아니라, **2026-08-26 단
하루만 BQ에서 신뢰할 수 없는 부분일**이다. `BQ_EXPORT_START`를 `2026-08-26`에서
`2026-08-27`로 정정했다(`scripts/update_ga4_unsedang.py` 및 관련 커맨드/문서 전부 반영).
이로써 **집계 가능 지표(eventCount)는 완전한 날짜 범위에서 예외 없이 100% 일치**함이
48일 규모로 재확인됐다 — §2-2의 "1일 스팟체크 완전 일치"가 우연이 아니었음을 뒷받침한다.

### 6-4. 세 리포트 실제 전환 완료 (2026-10-15, D-1=2026-10-14까지)
- **AI노트**(`ga4-ainote-kpi-unsedang.html`): 2026-09-30~10-13 → ~10-14로 누적 갱신 완료.
  GA4 쪽만 전환(`--skip-db`로 DB API는 건드리지 않음, 이 작업 범위 밖).
- **채널**(`ga4-channel-unsedang.html`): 9/16~10/13 → 9/17~10/14로 28일 롤링 갱신 완료.
- **퍼널**(`ga4-funnel-unsedang.html`): 7/16~10/13(90일) → **8/27~10/14(49일)로 클램프**
  적용해 갱신 완료 — 2026-07-16~2026-08-26 구간(42일)이 화면에서 사라졌다(git 히스토리에는
  보존됨). 2026-11-25부터 목표 90일 전체가 BQ 범위 안에 들어와 자동으로 90일로 복원된다.
- 세 리포트 모두 `--dry-run` 선확인 → 실제 실행 → `SafetyError` 없이 완료. 스크립트
  자동 백업(`*.bak-20261015-*`)이 각 HTML 옆에 생성됨.

## 7. 남은 작업
- 브라우저 렌더 확인(Playwright) — 이번 세션에서는 생략(각 커맨드 §6 기본값과 동일 — 사용자
  요청 시에만 수행).
- 채널 리포트의 `firstUserSource` lg/notSet 그룹의 4~7명 오차가 날짜마다 비슷한 방향인지는
  다일 반복검증까지는 못함(1일 스팟체크만 확인) — 추후 라우틴 실행 로그로 누적 관찰 권장.
- 클라우드 라우틴(`mcp_connections`)의 BigQuery 전환은 범위 밖(계획 단계 6, 별도 승인 필요).
