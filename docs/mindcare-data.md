## 호출 정보

- `https://admin.firstmindcare.com/api/v1/reports/mindcare-subscription-stats/monthly.json?baseMonth={YYYY-MM}`
- `carrierStats` 배열에 SKT, KT, LGU+ 세 통신사가 모두 포함되어 반환됨

## 실제 응답 필드 보정 (2026-09-18, 실API 확인)

아래 최초 작성된 스키마 예시에는 없었지만, 실제 응답에는 `premiumCumulative` /
`totalPremiumCumulative` 필드가 존재함 (유료/프리미엄/무료 3단계 구조). SKT는 현재 두 값이
항상 0이지만 KT·LGU+는 수만 단위의 유의미한 값을 가짐 — 리포트 작성 시 반드시 포함할 것.

```jsonc
{
  "baseMonth": "2026-09",              // 요청 파라미터로 받은 기준월 (YYYY-MM)
  "dateRange": {                       // 실제 집계 범위 (당월 진행 중이므로 1일~D-1일)
    "from": "2026-09-01",
    "to": "2026-09-15"
  },
  "carrierStats": [                    // 통신사별 배열 (SKT, KT, LGU+)
    {
      "carrier": "SKT",
      "totalPaidCumulative": 245600,     // 전체 유료누적 · 출처: 와이즈모니터
      "totalPremiumCumulative": 0,       // 전체 프리미엄누적 · 출처: 와이즈모니터 (SKT는 항상 0)
      "totalFreeCumulative": 1102340,    // 전체 무료누적 · 출처: 와이즈모니터
      "monthly": {                       // 기준월 시점 집계 (기준월당 1건)
        "paidCumulative": 241800,        // 월별 유료누적 · 출처: 와이즈모니터
        "premiumCumulative": 0,          // 월별 프리미엄누적 · 출처: 와이즈모니터
        "freeCumulative": 1078900,       // 월별 무료누적 · 출처: 와이즈모니터
        "transcriptionMeditationParticipants": 8340,     // 월별 필사명상 참여(인원)
        "transcriptionMeditationPoints": 15230000,       // 월별 필사명상 적립금(원)
        "dailyStats": [                  // dateRange 내 날짜별 배열
          {
            "date": "2026-09-01",
            "paidCumulative": 238900,
            "premiumCumulative": 0,
            "freeCumulative": 1042500,
            "transcriptionMeditationParticipants": 512,
            "transcriptionMeditationPoints": 940000
          }
          // ... dateRange.from ~ to 사이 날짜마다 반복
        ]
      }
    },
    {
      "carrier": "KT",                   // 아래는 SKT와 동일 구조 반복
      "totalPaidCumulative": 168200,
      "totalPremiumCumulative": 34500,
      "totalFreeCumulative": 890450,
      "monthly": {
        "paidCumulative": 165100,
        "premiumCumulative": 34500,
        "freeCumulative": 865200,
        "transcriptionMeditationParticipants": 6120,
        "transcriptionMeditationPoints": 11200000,
        "dailyStats": [
          {
            "date": "2026-09-01",
            "paidCumulative": 162400,
            "premiumCumulative": 34800,
            "freeCumulative": 838900,
            "transcriptionMeditationParticipants": 398,
            "transcriptionMeditationPoints": 705000
          }
        ]
      }
    },
    {
      "carrier": "LGU+",
      "totalPaidCumulative": 94500,
      "totalPremiumCumulative": 50300,
      "totalFreeCumulative": 402100,
      "monthly": {
        "paidCumulative": 92700,
        "premiumCumulative": 50300,
        "freeCumulative": 391200,
        "transcriptionMeditationParticipants": 3050,
        "transcriptionMeditationPoints": 5600000,
        "dailyStats": [
          {
            "date": "2026-09-01",
            "paidCumulative": 91100,
            "premiumCumulative": 51400,
            "freeCumulative": 382700,
            "transcriptionMeditationParticipants": 205,
            "transcriptionMeditationPoints": 360000
          }
        ]
      }
    }
  ]
}
```