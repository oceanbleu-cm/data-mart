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
    "totalChargeAmount": 128500000,      // 상담코인(CSL_PAID) 충전금액 합계 (운세 포인트 충전 제외, 원 단위)
    "totalRefundAmount": 3200000,        // 환불금액 합계 (운세·상담 유료 포인트 환불, 원 단위)
  
    // [상담 유형 정의] revenue / consultationCount / userCount / dailyStats 공통
    //   newConsultation           : 신규상담 - 고객의 전체 이력 중 최초 상담 1건
    //   repeatConsultation        : 재상담 - 신규상담을 제외한 나머지 전부 (당일 재상담 + 이후 재상담)
    //   sameDayRepeatConsultation : 당일 재상담 - 재상담 중 상담일이 그 고객의 신규상담일과 같은 건
    //   laterRepeatConsultation   : 이후 재상담 - 재상담 중 신규상담일 다음 날부터의 건
    //   revenue, consultationCount 에서 항상 성립:
    //     total = newConsultation + repeatConsultation
    //     repeatConsultation = sameDayRepeatConsultation + laterRepeatConsultation
    //   userCount 에서는 성립하지 않는다 (userCount 위 주석 참고)
    "revenue": {                         // 매출액 - 결제 방식별 구분 (신규/재상담, 재상담은 당일/이후로 다시 구분)
      "prepaid": {
        "total": 84200000,                        //   선불 매출 합계
        "newConsultation": 52300000,              //   선불 · 신규상담 매출
        "repeatConsultation": 31900000,           //   선불 · 재상담 매출 (당일 + 이후)
        "sameDayRepeatConsultation": 12400000,    //   선불 · 당일 재상담 매출
        "laterRepeatConsultation": 19500000       //   선불 · 이후 재상담 매출
      },
      "postpaid": {
        "total": 41100000,                        //   후불 매출 합계
        "newConsultation": 24500000,              //   후불 · 신규상담 매출
        "repeatConsultation": 16600000,           //   후불 · 재상담 매출 (당일 + 이후)
        "sameDayRepeatConsultation": 7300000,     //   후불 · 당일 재상담 매출
        "laterRepeatConsultation": 9300000        //   후불 · 이후 재상담 매출
      }
    },
    "consultationCount": {               // 상담 건수 - 결제 방식별 구분 (revenue 와 동일 구조)
      "prepaid": {
        "total": 6120,                            //   선불 건수 합계
        "newConsultation": 3450,                  //   선불 · 신규상담 건수
        "repeatConsultation": 2670,               //   선불 · 재상담 건수 (당일 + 이후)
        "sameDayRepeatConsultation": 1080,        //   선불 · 당일 재상담 건수
        "laterRepeatConsultation": 1590           //   선불 · 이후 재상담 건수
      },
      "postpaid": {
        "total": 2870,                            //   후불 건수 합계
        "newConsultation": 1620,                  //   후불 · 신규상담 건수
        "repeatConsultation": 1250,               //   후불 · 재상담 건수 (당일 + 이후)
        "sameDayRepeatConsultation": 520,         //   후불 · 당일 재상담 건수
        "laterRepeatConsultation": 730            //   후불 · 이후 재상담 건수
      }
    },
    // [userCount 주의] 한 유저가 여러 항목에 동시에 잡히므로 서로 더하면 안 된다.
    //   - 이번 달에 신규상담 후 재상담도 한 유저는 newConsultation 과 repeatConsultation 양쪽에 잡힌다
    //   - 선불과 후불을 모두 쓴 유저는 prepaid 와 postpaid 양쪽에 잡힌다 (prepaid.total + postpaid.total 은 전체 유저수가 아님)
    //   - 일자별 userCount 를 더해도 월 userCount 가 되지 않는다
    "userCount": {                       // 상담한 유저수 (중복 제외) - consultationCount 와 같은 구조
      "prepaid": {
        "total": 3980,                            //   선불 상담 유저수
        "newConsultation": 3450,                  //   선불 · 신규상담 유저수 (= 신규상담 건수)
        "repeatConsultation": 910,                //   선불 · 재상담 유저수
        "sameDayRepeatConsultation": 520,         //   선불 · 당일 재상담 유저수
        "laterRepeatConsultation": 610            //   선불 · 이후 재상담 유저수
      },
      "postpaid": {
        "total": 1840,                            //   후불 상담 유저수
        "newConsultation": 1620,                  //   후불 · 신규상담 유저수 (= 신규상담 건수)
        "repeatConsultation": 470,                //   후불 · 재상담 유저수
        "sameDayRepeatConsultation": 260,         //   후불 · 당일 재상담 유저수
        "laterRepeatConsultation": 280            //   후불 · 이후 재상담 유저수
      }
    },
  
    "topRevenueConsultants": [           // 매출액(신규+재상담) 기준 상담사 TOP5 (월 전체 기준, rank 오름차순, 매출 0 인 상담사 제외)
      // consultantId 는 상담사 고유번호(csl_key)를 문자열로 준다.
      // userCount 는 월 전체에 이 상담사와 상담한 유저수(중복 제외). 일자별 TOP5 의 userCount 를 더한 값과 다르다.
      { "rank": 1, "consultantId": "1024", "consultantName": "김상담", "revenueAmount": 5230000, "userCount": 38 },
      { "rank": 2, "consultantId": "1077", "consultantName": "이상담", "revenueAmount": 4980000, "userCount": 52 },
      { "rank": 3, "consultantId": "1003", "consultantName": "박상담", "revenueAmount": 4710000, "userCount": 45 },
      { "rank": 4, "consultantId": "1091", "consultantName": "최상담", "revenueAmount": 4402000, "userCount": 41 },
      { "rank": 5, "consultantId": "1055", "consultantName": "정상담", "revenueAmount": 4120000, "userCount": 29 }
    ],
    "topConsultationCountConsultants": [ // 상담 건수 기준 상담사 TOP5 (월 전체 기준, rank 오름차순, 건수 0 인 상담사 제외)
      { "rank": 1, "consultantId": "1003", "consultantName": "박상담", "consultationCount": 312, "userCount": 45 },
      { "rank": 2, "consultantId": "1024", "consultantName": "김상담", "consultationCount": 298, "userCount": 38 },
      { "rank": 3, "consultantId": "1077", "consultantName": "이상담", "consultationCount": 275, "userCount": 52 },
      { "rank": 4, "consultantId": "1055", "consultantName": "정상담", "consultationCount": 260, "userCount": 29 },
      { "rank": 5, "consultantId": "1091", "consultantName": "최상담", "consultationCount": 244, "userCount": 41 }
    ],
  
    "dailyStats": [                      // dateRange 내 날짜별 통계 배열 (요소 하나 = 하루치 데이터, 상담이 없는 날짜도 0 으로 포함)
      {
        "date": "2026-09-01",            // 해당 일자 (YYYY-MM-DD)
        "revenue": {                     // 해당 일자의 선불/후불 매출액 (월별 revenue 와 동일 구조)
          "prepaid": { "total": 2810000, "newConsultation": 1720000, "repeatConsultation": 1090000, "sameDayRepeatConsultation": 420000, "laterRepeatConsultation": 670000 },
          "postpaid": { "total": 1390000, "newConsultation": 830000, "repeatConsultation": 560000, "sameDayRepeatConsultation": 230000, "laterRepeatConsultation": 330000 }
        },
        "consultationCount": {           // 해당 일자의 선불/후불 상담 건수 (월별 consultationCount 와 동일 구조)
          "prepaid": { "total": 205, "newConsultation": 118, "repeatConsultation": 87, "sameDayRepeatConsultation": 34, "laterRepeatConsultation": 53 },
          "postpaid": { "total": 96, "newConsultation": 54, "repeatConsultation": 42, "sameDayRepeatConsultation": 17, "laterRepeatConsultation": 25 }
        },
        "userCount": {                   // 해당 일자의 상담 유저수 (월별 userCount 와 동일 구조, 더할 수 없는 값)
          "prepaid": { "total": 138, "newConsultation": 118, "repeatConsultation": 41, "sameDayRepeatConsultation": 17, "laterRepeatConsultation": 26 },
          "postpaid": { "total": 63, "newConsultation": 54, "repeatConsultation": 21, "sameDayRepeatConsultation": 9, "laterRepeatConsultation": 13 }
        },
        "topRevenueConsultants": [       // 해당 일자 매출액 기준 상담사 TOP5 (월별 항목과 동일 구조, userCount 포함 일 단위로 집계)
          { "rank": 1, "consultantId": "1024", "consultantName": "김상담", "revenueAmount": 320000, "userCount": 9 }
          // ... rank 2~5 생략 (실제 응답에는 최대 5건까지 포함, 해당 일자에 상담이 없으면 빈 배열)
        ],
        "topConsultationCountConsultants": [ // 해당 일자 상담 건수 기준 상담사 TOP5
          { "rank": 1, "consultantId": "1003", "consultantName": "박상담", "consultationCount": 18, "userCount": 11 }
          // ... rank 2~5 생략
        ]
      }
    ]
}