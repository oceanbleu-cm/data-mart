# GA4 + Supermetrics 작업 지침서 (Claude Code용)

이 문서는 claude.ai에서 GA4 데이터를 Supermetrics로 분석하며 쌓인 실전 노하우를 정리한 것입니다.
Claude Code에서 같은 작업을 이어갈 때 참고하세요.

---

## 1. 연결된 계정 목록 (Supermetrics GAWA, 팀: cfguyk7@gmail.com)

| account_id | 계정명 | 그룹 | 용도/특징 |
|---|---|---|---|
| 488612198 | unsedang-a3588 | wisesolution | 운세당(운세/사주 서비스) 메인 프로퍼티 |
| 488598213 | unsedang-dev | wisesolution | 개발/테스트용, 분석 대상 아님 |
| 295084110 | MINDCARE | wisesolution | 마인드케어(명상/심리상담 서비스) |
| 533931964 | wisemindcare | wisesolution | 미사용 |
| 372872455 | KT_PASS_TODAY - GA4 | wisesolution | KT PASS 부가서비스용 |
| 384055746 | PASS운세_신규 - GA4 | wisesolution | PASS 운세 부가서비스 (Google Signals 미설정 상태, 성별/연령 데이터 없음) |
| 517885233 | pass-cloud-c6850 | wisesolution | 미확인 |
| 373209975 | web.wisetoday.kr - GA4 | wisesolution | 운세당/마인드케어와 자매 서비스("투데이"), 상호 트래픽 유입 관계 |

**참고**: 계정을 못 찾으면 `accounts_discovery`에 다양한 키워드(영문/한글, 부분 문자열)로 재시도. 예를 들어 "healthcare"는 실패했지만 "pass"는 성공한 사례가 있었음.

---

## 2. Supermetrics 쿼리 문법 — 실전에서 겪은 함정들

### 2-1. 필터 연산자
```
==   정확히 일치
!=   정확히 일치하지 않음 (AND로 여러 조건 결합 가능, 안정적으로 작동)
=@   포함 (contains)
!@   포함하지 않음 (⚠️ 아래 버그 참고)
```
**연산자 양쪽에 반드시 공백 필요**: `country == 'United States'` (O), `country=='United States'` (X, 에러 발생)

### 2-2. ⚠️ 치명적 버그: `!@` 필터는 해당 필드가 dimension으로 포함되지 않으면 무시됨
- **증상**: `pagePath !@ 'X'`처럼 필터만 걸고 `pagePath`를 dimension으로 안 넣으면, 필터가 조용히 무시되고 전체 미필터 값이 반환됨 (에러 없음, 그냥 틀린 결과가 나옴)
- **해결**: 집계값(dimension 없이 합계만 구할 때)을 제외하고 싶으면 `!=`(정확히 일치하지 않음) 연산자를 쓸 것. 이건 dimension 포함 여부와 무관하게 정상 작동함.
- **검증 방법**: 같은 조건으로 필터 있음/없음 두 번 조회해서 숫자가 동일하면 필터가 무시된 것 → `!=` 로 바꿔서 재시도

### 2-3. pagePath 계열 필드 이름 주의
- `pagePathWithoutQueryString`: 쿼리스트링 제외, **끝에 슬래시 유무가 실제 값과 다를 수 있음** (예: `/kpass/news2` vs `/kpass/news2/` — 사이트마다 다름, 먼저 확인 필요)
- `pagePath`: 쿼리스트링 포함
- `landingPage`: **세션의 첫 페이지**(방문 페이지) 기준, GA4 UI의 "방문 페이지" 리포트와 동일
- `landingPagePlusQueryString`: 위 + 쿼리스트링

**"페이지 및 화면" vs "방문 페이지"는 완전히 다른 지표** — 전자는 세션 중 한 번이라도 본 모든 페이지(중복 카운트 가능), 후자는 세션이 시작된 페이지만. 같은 페이지라도 값이 수십~수백 배 차이 날 수 있음 (실제 사례: `/authfail` 페이지 및 화면 기준 25,755명 vs 방문 페이지 기준 1,105명).

### 2-4. 비집계(non-aggregatable) 지표 주의
`totalUsers`, `activeUsers`, `bounceRate`, `engagementRate`, `sessionsPerUser` 등은 **dimension으로 쪼갠 여러 행을 사람이 직접 더하면 안 됨** (같은 사용자가 여러 행에 중복 포함되어 실제보다 크게 나옴). 합계가 필요하면:
- dimension 없이 별도로 재조회 (GA4가 직접 정확히 계산해줌)
- 또는 `!=` 필터로 제외 조건을 걸어서 원하는 범위의 정확한 합계를 직접 조회

### 2-5. 날짜/기간
- `date_range_type: "custom"` + `start_date`/`end_date` (YYYY-MM-DD)
- 프리셋: `last_7_days_inc`, `last_30_days_inc`, `last_90_days_inc`, `yesterday` 등
- 오늘 날짜 확인: `get_today` 툴 사용 (상대 날짜 계산 전 필수)
- 월별 집계는 `yearMonth` dimension 사용 (형식: `2026|08`)

### 2-6. 검색 시 존재하지 않는 경로 주의
요청받은 path가 실제로 없을 수 있음 (예: `/topicList` 요청 → 실제로는 `/topicList/ALL`). `=@`(포함)으로 먼저 탐색해서 정확한 실제 경로를 확인한 뒤 정확한 필터를 걸 것.

---

## 3. 자주 쓰는 GA4 필드 모음

| 필드 ID | 설명 |
|---|---|
| `activeUsers` | 활성사용자 (session_start/first_visit/참여 이벤트 발생 기준) |
| `totalUsers` | 총사용자 (이벤트 1개 이상) |
| `active28DayUsers` | 28일 롤링 MAU (진짜 "Monthly Active Users" 정의에 가장 가까움, 캘린더 월과 다름) |
| `sessions` | 세션수 (유일하게 dimension 쪼개도 안전하게 합산 가능) |
| `bounceRate` | 이탈율 (비참여 세션 비율, 비집계 지표) |
| `sessionDefaultChannelGroup` | 유입 채널 분류 (Direct/Organic Search/Display 등) |
| `sessionManualSource` / `sessionManualMedium` | UTM 기반 수동 소스/매체 |
| `pageReferrer` | 전체 리퍼러 URL |
| `userGender` / `userAgeBracket` | 성별/연령대 — **Google 신호 데이터(Google Signals) 활성화 필수**, 활성화 후 시점부터만 데이터 쌓임 (소급 불가) |
| `eventName` | 커스텀 이벤트명 필터링 시 사용 |

---

## 4. 서비스별 핵심 페이지/이벤트 정의

### unsedang.com (운세당)
- `/view/home`: 홈메인
- `/view/csl`: 상담사 목록
- `/view/csl/cslInfo?cslKey=N`: 상담사 상세 (N = 상담사 ID). `pagePathWithoutQueryString`으로 조회하면 쿼리스트링 없이 `/view/csl/cslInfo`로 정확히 합쳐짐(끝 슬래시 없음, 2026-09-21 실측 확인) — 이 페이지 자체가 "상세페이지 진입" 이벤트 역할
- `/view/free`, `/view/free/registrationStart`, `/registrationForm`, `/registrationEnd`: 쪽지상담 4단계 (끝 슬래시 없는 형태로 실측 확인)
- `/view/content`, `/view/fortune/unseYear` 등: 운세 콘텐츠
- **전화클릭/클릭 이벤트 체계 (2026-09-21 실측 및 사용자 확인으로 정정)**:
  - `pre_tel_click`: **선불상담** 전화클릭. `_mobile`/`_pc`/`_res_false` 변형 존재, 전부 `/view/csl/cslInfo`에서 발생. **2026-06부터 신규 집계 시작** (그 이전 데이터 없음)
  - `post_tel_click`: **후불상담** 전화클릭. 동일한 변형 존재, `/view/csl/cslInfo`와 `/view/home` 양쪽에서 발생(2026-09 기준 최근 30일 사이 `/view/home` 비중이 더 큼 — 홈에도 별도 전화 진입 경로가 있는 것으로 추정). 2026-01부터 집계됨. **6월 이후 건수 급감은 실사용 감소가 아니라 선불/후불 버튼 분리 도입으로 인한 집계 방식 변경 가능성이 높음** — 월별 비교 시 반드시 감안할 것
  - `coach_mark_main_click`: **홈 화면에서 상담사 선생님(코치마크) 클릭**. 거의 전량 `/view/home`에서 발생. **2026-03부터 신규 집계 시작**
  - `main_banner_click`: **홈 히어로 섹션 배너 클릭**. `/view/home`에서 발생. 2026-01부터 집계됨
  - ⚠️ 과거 "pre_(구)/post_(신) 교체" 가설은 틀림 — 실제로는 선불/후불이라는 서로 다른 결제방식을 가리키는 별개 이벤트이며, 오히려 `pre_`가 `post_`보다 나중(6월)에 도입됨
  - `activeUsers`를 이벤트별로 합산 집계할 때는 `_mobile`/`_pc`/`_res_false` 변형을 전부 포함하되, `eventName` dimension 없이(예: `eventName =@ 'pre_tel_click' AND pagePathWithoutQueryString == '/view/csl/cslInfo'`) 재조회해야 정확한 순사용자 수가 나옴 — dimension 포함 상태로 나온 변형별 값을 사람이 더하면 안 됨(§2-4 원칙과 동일)
- GTM 컨테이너: `GTM-5KCGHNWV` (계정 "운세당", 컨테이너 ID `232663874`)

### MINDCARE
- `/breathing`: 숨명상 메인 (⚠️ `/breathlist`와 다른 페이지, 혼동 주의)
- `/transcription01~03`: 필사명상
- `/topicList/ALL`: 명상 콘텐츠
- `/main/2,3,4`: 마음관찰/마음케어/마음상담
- **`/kpass/news2/`, `/kpass/recommend/`**: 전체 트래픽의 압도적 다수(월 75~95%)를 차지하는 페이지. 실제 콘텐츠 소비가 아닌 백그라운드성 호출로 추정됨. **전체 서비스 규모를 볼 때는 반드시 이 2개를 제외**하고 봐야 실제 이용 현황이 보임.

---

## 5. GA4 UI 관련 참고사항

- **탐색 분석(Explore)**: 데이터 보관 기간(Data Retention, 조직 설정에 따라 2개월 또는 14개월) 제한 있음 — 과거 데이터가 갑자기 선택 불가능해지면 이 제한 때문.
- **표준 리포트**: 위 제한 없음, 항상 전체 히스토리 조회 가능. 과거 데이터 확인은 표준 리포트로.
- **진짜 순차 퍼널(단계별 이탈률 포함)**: API로는 불가능. GA4 UI의 **탐색 분석 → 유입경로 탐색(Funnel Exploration)**에서만 가능.
- GA4 필터 UI에서 "Click Element" 같은 요소 기반 조건은 실제 DOM 구조가 바뀌면 쉽게 깨짐 (GTM 트리거 디버깅 시 특히 주의, "Click Classes"가 더 안정적).

---

## 6. BigQuery 연동 관련 (참고, 현재 보류 상태)

- unsedang.com은 GA4→BigQuery 연동됨 (`analytics_488612198` 데이터셋), 단 연동 시작일(대략 8/26) 이후 데이터만 존재.
- 조직 정책(`iam.allowedPolicyMemberDomains`, "도메인 제한 공유")으로 개인 Gmail 계정에 IAM 권한 부여가 막혀 있었음. 실제 개인 Gmail 계정을 위한 정확한 고객 ID는 공개되지 않아, 임시로 정책을 완화("모든 값 허용")한 뒤 권한 부여 후 즉시 원복하는 방식이 필요.
- 장기적으로는 회사 도메인 계정(예: @wisesolution.co.kr 형태)으로 전환하는 게 정책 예외 없이 가장 깔끔한 해결책.

---

## 7. 작업 시 체크리스트

1. 계정 전환 시 `accounts_discovery`로 정확한 account_id 재확인
2. 새로운 path/이벤트 요청 시 `=@`로 먼저 탐색해서 정확한 실제 값 확인
3. 사용자 수 지표(활성/총사용자)의 합계가 필요하면 반드시 dimension 없이 별도 재조회
4. `!@` 필터는 dimension 없이 쓰면 무시될 수 있음 → `!=`로 대체
5. 월별/기간별 비교 시, 일수가 다르면(예: Before 6일 vs After 2일) 반드시 "1일 평균"으로 환산해서 비교
6. 결과를 시트로 저장할 때는 `create_file`의 `textContent` 파라미터 사용 (한글 포함 시 `base64Content`는 인코딩 오류 잦음)
