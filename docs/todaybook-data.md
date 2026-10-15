# GA4 이벤트 추적 가이드

> 출처: `오늘의 지식 리포트 데이터 수집 요청서 (GA·DB)` (2026-10-13, @JEONGHYUN)

## 공통 조건

| 항목 | 내용 |
|---|---|
| GA4 속성 | `properties/556152838` (오늘의 지식) |
| 호출 API | GA4 Data API `runReport` |
| 수집 주기 | 매일 오전, 전일(D-1) 데이터 저장 |
| 보정 | 매일 최근 3일치를 다시 조회해 덮어쓰기 (GA 데이터 확정에 최대 24~48시간) |
| 기준 시간대 | `Asia/Seoul` (GA 속성 시간대 확인 필요, DB 일자 기준과 일치) |
| 통신사 필터 | `hostName = web.todaybook.kr` (SKT). KT·LGU+ 도메인이 생기면 hostName만 바꿔 같은 요청 반복 |
| 저장 단위 | 일자 × 통신사 1행 |
| 맞춤 측정기준 호출명 | 이벤트 범위 `customEvent:파라미터명`, 사용자 범위 `customUser:속성명` (GA 화면 표시명 아님) |
| 수집 시작일 | 서비스 오픈일 2026-10-13부터 소급 저장 |

## GA 수집 항목 (저장 컬럼 9개)

모든 행에 공통 필터(`hostName`)가 추가로 들어간다.

| 리포트 지표 | 저장 컬럼 | 조회 기간 | 측정항목(metric) | 필터(dimensionFilter) |
|---|---|---|---|---|
| 4. DAU | `dau` | 해당일 1일 | `activeUsers` | 공통 필터만 |
| 4. DAU(유료) | `dau_paid` | 해당일 1일 | `activeUsers` | `customUser:member_status = paid` |
| 4. 월 누적 MAU | `mau_to_date` | **해당 월 1일 ~ 해당일** | `activeUsers` | 공통 필터만 |
| 6. 지식카드 읽은 사람 | `card_read_users` | 해당일 1일 | `totalUsers` | `eventName = content_read_complete` AND `customEvent:content_type = knowledge_card` |
| 7. 북노트 읽은 사람 | `booknote_read_users` | 해당일 1일 | `totalUsers` | `eventName = content_read_complete` AND `customEvent:content_type = booknote` |
| 7. 북챗 이용자 | `bookchat_users` | 해당일 1일 | `totalUsers` | `eventName = bookchat_start` |
| 8. 도서 이용자 | `book_users` | 해당일 1일 | `totalUsers` | `eventName = book_open` |
| 8. 전자책 이용자 | `ebook_users` | 해당일 1일 | `totalUsers` | `eventName = book_open` AND `customEvent:format = ebook` |
| 8. 오디오북 이용자 | `audiobook_users` | 해당일 1일 | `totalUsers` | `eventName = book_open` AND `customEvent:format = audiobook` (값 확인 필요) |

**주의:** 사용자 수(`activeUsers` · `totalUsers`)는 더하면 안 된다. 일별 값은 일별로, 월 누적은 월 기간(월 1일 ~ 해당일)으로 따로 조회한다. 같은 이유로 일별 표에 합계 행을 두지 않으며, 도서 이용자는 전자책 + 오디오북보다 작다(둘 다 이용한 사람은 한 번만 셈).

## 계산 컬럼 (GA 재조회 없이 저장값으로 계산)

| 리포트 지표 | 저장 컬럼 | 계산식 | 비고 |
|---|---|---|---|
| 5. 유료회원 활성률 | `paid_active_rate` | `dau_paid ÷ 유료 누적가입자(해당일, DB)` | DB 값과 일자 기준 일치 필요, 소수점 둘째 자리 % |

## 요청 예시

`card_read_users`(지식카드 읽은 사람) 하루치 조회 예시. 다른 항목은 위 표의 측정항목과 필터만 바꾸면 된다.

```
POST https://analyticsdata.googleapis.com/v1beta/properties/556152838:runReport
{
  "dateRanges": [{ "startDate": "2026-10-13", "endDate": "2026-10-13" }],
  "metrics": [{ "name": "totalUsers" }],
  "dimensionFilter": {
    "andGroup": { "expressions": [
      { "filter": { "fieldName": "hostName", "stringFilter": { "value": "web.todaybook.kr" } } },
      { "filter": { "fieldName": "eventName", "stringFilter": { "value": "content_read_complete" } } },
      { "filter": { "fieldName": "customEvent:content_type", "stringFilter": { "value": "knowledge_card" } } }
    ]}
  }
}
```

여러 날을 한 번에 받을 때는 `dimensions`에 `date`를 넣으면 날짜별 행으로 나뉜다. 단, `mau_to_date`는 반드시 월초~해당일 기간으로 해당일마다 따로 조회한다.

## 화면 표기

사용자 수 컬럼은 일별 표 합계 행에 "–"로 표시하고, 월 값은 요약 카드에 `mau_to_date` 최신값으로 보여준다 (투데이 리포트의 누적가입자 표기 방식과 동일).

## 개발 전 확인 사항

- [x] 서비스 계정에 GA4 속성(556152838) '뷰어' 권한 부여 — Supermetrics MCP로 조회 가능 확인(2026-10-15)
- [ ] GA 속성 시간대가 `Asia/Seoul`인지 확인 — 미확인, Supermetrics `date` 디멘션은 속성 시간대 기준이므로 추가 조치 불필요할 가능성
- [x] API에서 `customEvent:content_type`가 조회되는지 확인 → **GA4 표준 디멘션 `contentType`으로 조회 가능**(지식카드/북노트 구분 확인됨)
- [ ] `customEvent:format`, `customUser:member_status` → **Supermetrics GAWA 커넥터가 패스스루하지 않아 조회 불가**(아래 참고)
- [ ] `book_open`의 오디오북 format 값 확인 — `format` 자체를 조회할 수 없어 보류

## Supermetrics 실측 확인 (2026-10-15)

Supermetrics 플랜의 GA4 "우선 계정" 3개 한도에 걸려 있던 것을 해제하고(기존
unsedang-a3588/MINDCARE/헬스케어 → 헬스케어 자리에 `556152838`todaybook 교체,
`manage_user_and_team` set_prioritised_accounts) 실측 쿼리한 결과:

| 요청서 항목 | 판정 | 비고 |
|---|---|---|
| `hostName` 필터 | ✅ 사용 가능 | `web.todaybook.kr` 외 `dev.todaybook.kr`/`localhost`/`api.todaybook.kr`/`dapi.todaybook.kr` 트래픽이 섞여 들어와 **필터 필수** 확인 |
| `dau`(activeUsers) | ✅ 조회됨 | |
| `card_read_users`/`booknote_read_users` | ✅ 조회됨 | `customEvent:content_type`이 아니라 GA4 표준 디멘션 `contentType`으로 `content_read_complete` 이벤트를 `knowledge_card`/`booknote`로 구분(디멘션에 반드시 포함해야 필터가 먹음) |
| `bookchat_users`(`bookchat_start`) | ✅ 조회됨 | |
| `book_users`(`book_open`) | ✅ 조회됨 | |
| `dau_paid`(customUser:member_status) | ❌ 조회 불가 | Supermetrics GAWA가 GA4 맞춤 사용자 속성을 패스스루하지 않음(`field_discovery`에 `member`/`status`/`audience` 계열 전무) |
| `ebook_users`/`audiobook_users`(customEvent:format) | ❌ 조회 불가 | 위와 동일 사유, `format` 커스텀 이벤트 파라미터도 패스스루 없음 |
| `mau_to_date` | ⚠️ 정의 수정 | 아래 참고 |

**해소 경로(나중에, 별도 작업)**: ① `dau_paid` — GA4에서 "유료회원"(member_status=paid)
잠재고객(Audience)을 만들어 Supermetrics `audienceName` 디멘션으로 조회(소급 불가,
생성 시점부터). ② `ebook`/`audiobook` — GTM에서 `book_open_ebook`/`book_open_audiobook`처럼
**이벤트명 자체를 분리**하면 `eventName`으로 바로 잡힘(가장 확실). 또는 요청서 원안대로
GA4 Data API를 서비스 계정으로 직접 호출(이 저장소에 해당 클라이언트 없음 — 신규 의존성).

**`mau_to_date` 정의 수정**: 서비스 오픈(2026-10-13) 이전에도 `web.todaybook.kr`
호스트에서 QA/사전 트래픽이 실제로 잡혀 있다(10/1~10/12, 일별 2~13명 — 실측 확인).
요청서 원문(월초~해당일)대로 계산하면 10/13의 `mau_to_date`(57)가 같은 날 DAU(40)보다
커지는 역전이 생긴다. **오픈일 고정 시작 원칙**(§ GA 수집 항목 "수집 시작일")을 그대로
적용해 `mau_to_date` 집계 시작일을 `max(그 달 1일, 2026-10-13)`로 클램프하기로
결정(2026-10-15, 사용자 승인) — 클램프 적용 시 10/13=40(DAU와 동일), 10/14=44.

## 참고 / 주의사항

- 가입 화면(`web.wisetoday.kr`)에는 GTM이 없어 **가입 완료는 GA로 잡히지 않는다.** 가입·해지·유료 누적·알림 신청자·쿠폰 신청건수는 전부 DB에서 가져온다 (아래 "DB 수집 항목" 참고).
- 데이터 임곗값: Google 신호가 켜져 있으면 사용자 수가 적은 날 값이 비어서 올 수 있다. 응답에 값이 빠지면 GA 관리 > 보고 ID 설정 확인.

## DB 수집 항목 (참고 — GA 아님)

가입·해지·알림·쿠폰은 DB에서 일자별(00:00~23:59, KST)로 집계해 저장한다. 스냅샷은 해당일 23:59 기준 값, 일 합계는 그날 발생한 건수다.

| 리포트 지표 | 저장 컬럼 | 정의 | 집계 방식 |
|---|---|---|---|
| 1. 유료 누적가입자 | `paid_total` | 이용중(유료) 회원 수 | 스냅샷 |
| 1. 전일 대비 증감 | `paid_total_diff` | `paid_total − 전일 paid_total` | 계산 |
| 2. 신규 가입 | `join_total` | 가입 완료 건수 (해지 후 재가입 포함) | 일 합계 |
| 3. 해지 | `cancel_total` | 해지 완료 건수 | 일 합계 |
| 3. 해지율 | `churn_rate` | `cancel_total ÷ 전일 paid_total (%)` | 계산 |
| 9. 지식카드 알림 신청자 | `noti_on_total` | 지식카드 알림 ON인 유료회원 수 | 스냅샷 |
| 10. 쿠폰 신청건수 | `coupon_apply_count` | 쿠폰 신청(발급) 건수 | 일 합계 |

검증: `paid_total_diff`는 `join_total − cancel_total`과 같아야 한다. 다르면 화면 하단에 불일치 표시 (투데이 리포트의 "월 API 합계와 일치" 표시와 같은 방식).

---

# GA4 집계 이벤트


https://api.todaybook.kr/api/v1/reports/todaybook-subscription-stats/monthly.json?baseMonth={YYYY-MM}

{
  "baseMonth": "2026-10",
  "dateRange": {
    "from": "2026-10-01",
    "to": "2026-10-14"
  },
  "carrierStats": [
    {
      "carrier": "SKT",
      "totalPaidCumulative": 3,
      "monthly": {
        "paidCumulative": 3,    // 유로 누적
        "paidJoin": 9,  // 가입
        "paidCancel": 9,    // 해지
        "dailyStats": [
          {
            "date": "2026-10-01",
            "paidCumulative": null,
            "paidJoin": null,
            "paidCancel": null
          },
          {
            "date": "2026-10-02",
            "paidCumulative": null,
            "paidJoin": null,
            "paidCancel": null
          }
        ]
      }
    }
  ]
}
