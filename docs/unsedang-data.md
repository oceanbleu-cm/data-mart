# unsedang.com GA4 (unsedang-a3588) 퍼널 측정 기준 
# page_path, event 기준
# 각 퍼널에 단계별 사용자 이동 흐름 퍼널데이터 지표 측정

## 홈메인 퍼널 (2026-09-21 정정: docs/ga4_guide.md §4 이벤트 체계 참고)
1-1: /view/home 진입
1-1 참고 이벤트(순차 아님, 홈 화면 내 클릭): coach_mark_main_click(상담사 선생님 클릭, 2026-03~), main_banner_click(히어로 배너 클릭, 2026-01~)
1-2: /view/csl/cslInfo 진입 (상세페이지 진입)
1-2 참고 이벤트(순차 아님, 상세페이지 전화클릭): pre_tel_click(선불상담, 2026-06~), post_tel_click(후불상담, 2026-01~)
## 상담페이지 퍼널
2-1: /view/csl
2-2: /view/csl/cslInfo (상세페이지 진입)
2-2 참고 이벤트: pre_tel_click(선불상담), post_tel_click(후불상담) — 위와 동일
## 쪽지상담 퍼널
3-1: /view/free
3-2: /view/free/registrationStart
3-3: /view/free/registrationForm
3-4: /view/free/registrationEnd
## 운세
4-1: /view/content
4-2: /view/fortune/unseYear


# 매출 json 데이터 기준
# https://adm.unsedang.com/api/v1/reports/consultation-stats/monthly?baseMonth=2026-09
# baseMonth=2026-09 파라미터 변경 조회 가능

{
  "baseMonth": "2026-09",              // 요청 파라미터로 받은 기준월 (YYYY-MM)
  "dateRange": {                       // 실제 집계에 사용된 날짜 범위 (당월이면 1일~D-1일, 완료된 과거월이면 1일~말일)
    "from": "2026-09-01",
    "to": "2026-09-14"
  },
  "totalChargeAmount": 128500000,      // 전체 충전금액 (선불/후불 구분 없이 월 전체 합계, 원 단위)
  "totalRefundAmount": 3200000,        // 전체 환불금액 (월 전체 합계, 원 단위)

  "revenue": {                         // 매출액 - 결제 방식별 구분 (신규/재상담 세부 breakdown 포함)
    "prepaid": {
      "total": 84200000,               //   선불 매출액 합계
      "newConsultation": 52300000,     //   선불 · 신규상담 매출
      "repeatConsultation": 31900000   //   선불 · 재상담 매출
    },
    "postpaid": {
      "total": 41100000,               //   후불 매출액 합계
      "newConsultation": 24500000,     //   후불 · 신규상담 매출
      "repeatConsultation": 16600000   //   후불 · 재상담 매출
    }
  },
  "consultationCount": {               // 상담 건수 - 결제 방식별 구분 (신규/재상담 세부 breakdown 포함)
    "prepaid": {
      "total": 6120,                   //   선불 상담 건수
      "newConsultation": 3450,         //   선불 · 신규상담 건수
      "repeatConsultation": 2670       //   선불 · 재상담 건수
    },
    "postpaid": {
      "total": 2870,                   //   후불 상담 건수
      "newConsultation": 1620,         //   후불 · 신규상담 건수
      "repeatConsultation": 1250       //   후불 · 재상담 건수
    }
  },

  "topRevenueConsultants": [           // 매출액 기준 상담사 TOP5 (월 전체 기준, rank 오름차순 정렬)
    { "rank": 1, "consultantId": "C1024", "consultantName": "김상담", "revenueAmount": 5230000 },
    { "rank": 2, "consultantId": "C1077", "consultantName": "이상담", "revenueAmount": 4980000 },
    { "rank": 3, "consultantId": "C1003", "consultantName": "박상담", "revenueAmount": 4710000 },
    { "rank": 4, "consultantId": "C1091", "consultantName": "최상담", "revenueAmount": 4402000 },
    { "rank": 5, "consultantId": "C1055", "consultantName": "정상담", "revenueAmount": 4120000 }
  ],
  "topConsultationCountConsultants": [ // 상담 건수 기준 상담사 TOP5 (월 전체 기준, rank 오름차순 정렬)
    { "rank": 1, "consultantId": "C1003", "consultantName": "박상담", "consultationCount": 312 },
    { "rank": 2, "consultantId": "C1024", "consultantName": "김상담", "consultationCount": 298 },
    { "rank": 3, "consultantId": "C1077", "consultantName": "이상담", "consultationCount": 275 },
    { "rank": 4, "consultantId": "C1055", "consultantName": "정상담", "consultationCount": 260 },
    { "rank": 5, "consultantId": "C1091", "consultantName": "최상담", "consultationCount": 244 }
  ],

  "dailyStats": [                      // dateRange 내 날짜별 통계 배열 (요소 하나 = 하루치 데이터)
    {
      "date": "2026-09-01",            // 해당 일자 (YYYY-MM-DD)
      "revenue": {                     // 해당 일자의 선불/후불 매출액 (신규/재상담 breakdown 포함)
        "prepaid": { "total": 2810000, "newConsultation": 1720000, "repeatConsultation": 1090000 },
        "postpaid": { "total": 1390000, "newConsultation": 830000, "repeatConsultation": 560000 }
      },
      "consultationCount": {           // 해당 일자의 선불/후불 상담 건수 (신규/재상담 breakdown 포함)
        "prepaid": { "total": 205, "newConsultation": 118, "repeatConsultation": 87 },
        "postpaid": { "total": 96, "newConsultation": 54, "repeatConsultation": 42 }
      },
      "topRevenueConsultants": [       // 해당 일자 매출액 기준 상담사 TOP5 (월별 항목과 동일 구조, 일 단위로 집계)
        { "rank": 1, "consultantId": "C1024", "consultantName": "김상담", "revenueAmount": 320000 }
        // ... rank 2~5 생략 (실제 응답에는 최대 5건까지 포함)
      ],
      "topConsultationCountConsultants": [ // 해당 일자 상담 건수 기준 상담사 TOP5
        { "rank": 1, "consultantId": "C1003", "consultantName": "박상담", "consultationCount": 18 }
        // ... rank 2~5 생략
      ]
    }
  ]
}