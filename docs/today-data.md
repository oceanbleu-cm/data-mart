## 호출 정보 (2026-09-18 기준 갱신)

- KT (`html/db-data-kt-today.html`): `https://admin.wisetoday.kr/api/v1/reports/carrier-subscription-stats/monthly.json?baseMonth={YYYY-MM}`
  - `carrierStats` 배열에 KT, LGU+ 두 통신사가 모두 포함되어 반환됨 (순서: KT가 index 0) → 프론트에서는 `carrierStats[0]`만 사용
- LGU+ (`html/db-data-lg-today.html`): `http://34.64.151.91:9202/api/v1/reports/carrier-subscription-stats/monthly.json?baseMonth={YYYY-MM}`
  - KT와 다른 호스트(내부 IP:9202)이며, `carrierStats` 배열에 LGU+ 단일 통신사만 반환됨 → 프론트에서는 `carrierStats[0]`만 사용
- 과거 사용되던 `telCd=KT` / `telCd=LGU` 쿼리 파라미터는 더 이상 쓰이지 않음 — 통신사는 호출 호스트 자체로 구분됨

## 응답 바디 예시 (스키마는 두 엔드포인트 공통, `carrierStats` 배열 길이만 다름)

```jsonc
{
  "baseMonth": "2026-09",              // 요청 파라미터로 받은 기준월 (YYYY-MM)
  "dateRange": {                       // 실제 집계 범위 (당월 진행 중이므로 1일~D-1일)
    "from": "2026-09-01",
    "to": "2026-09-15"
  },
  "carrierStats": [                    // 통신사별 배열 — KT 엔드포인트: [KT, LGU+] 2건 / LGU+ 엔드포인트: [LGU+] 1건
    {
      "carrier": "KT",
      "totalPaidCumulative": 182340,   // 전체 유료누적 · 출처: 와이즈모니터
      "totalFreeCumulative": 941820,   // 전체 무료누적 · 출처: 와이즈모니터
      "monthly": {                     // 기준월 시점 집계 (기준월당 1건)
        "paidCumulative": 178920,      // 월별 유료누적 · 출처: 와이즈모니터
        "freeCumulative": 918450,      // 월별 무료누적 · 출처: 와이즈모니터
        "cashbackSubscriberCount": 5230,   // 월별 복돈받기 알림자 수
        "cashbackPayoutCount": 4870,       // 월별 복돈받기 지급인원 · 출처: DBeaver
        "cashbackPayoutAmount": 24350000,  // 월별 복돈받기 지급금액(원) · 출처: DBeaver
        "dailyStats": [                // "일매출" — dateRange 내 날짜별 배열
          {
            "date": "2026-09-01",
            "paidCumulative": 176210,
            "freeCumulative": 902110,
            "cashbackSubscriberCount": 340,
            "cashbackPayoutCount": 315,
            "cashbackPayoutAmount": 1575000
          }
          // ... dateRange.from ~ to 사이 날짜마다 반복
        ]
      }
    },
    {
      "carrier": "LGU+",                // 아래는 KT와 동일 구조 반복
      "totalPaidCumulative": 96110,
      "totalFreeCumulative": 402330,
      "monthly": {
        "paidCumulative": 94020,
        "freeCumulative": 391870,
        "cashbackSubscriberCount": 2110,
        "cashbackPayoutCount": 1960,
        "cashbackPayoutAmount": 9800000,
        "dailyStats": [
          {
            "date": "2026-09-01",
            "paidCumulative": 92980,
            "freeCumulative": 385410,
            "cashbackSubscriberCount": 140,
            "cashbackPayoutCount": 128,
            "cashbackPayoutAmount": 640000
          }
        ]
      }
    }
  ]
}
```