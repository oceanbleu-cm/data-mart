## 호출 정보

⚠️ 아래 "호출 정보" 절(2026-09-18 작성)과 실제 라이브 코드(`html/db-data-today.html`,
2026-09-23 기준)가 서로 다르다 — 미해결 상태로 남겨둠, 실제 API 스펙 재확인 필요:
- 이 문서: 호스트로 통신사 구분(KT는 `admin.wisetoday.kr`, LGU+는 내부IP `34.64.151.91:9202`),
  `telCd` 파라미터는 폐기됨이라고 기술.
- 라이브 코드: 동일 호스트(`admin.wisetoday.kr`)에 `telCd=KT`/`telCd=LGU` 쿼리 파라미터로
  구분 — 2026-09-23 세션에서 브라우저 실호출로 정상 동작(200 응답, 통신사별 다른 값) 확인됨.
- `html/db-data-lg-today.html`이 2026-09-21 세션 중 "외부에서" 변경된 이력이 있음
  (daylog 2026-09-21 참고) — 이 문서와 라이브 코드 간 불일치가 그 변경과 관련된 것으로 추정되나 미확인.

- KT/LGU+ (`html/db-data-today.html`, 통신사 탭으로 통합·기본값 KT): `https://admin.wisetoday.kr/api/v1/reports/carrier-subscription-stats/monthly.json?baseMonth={YYYY-MM}`
  - `carrierStats` 배열에 KT, LGU+ 두 통신사가 모두 포함되어 반환됨 (순서: KT가 index 0) → 프론트에서는 `carrierStats[0]`만 사용
  - (문서상 구식 정보, 라이브 코드와 불일치 — 위 경고 참고) LGU+: `http://34.64.151.91:9202/api/v1/reports/carrier-subscription-stats/monthly.json?baseMonth={YYYY-MM}`
    - KT와 다른 호스트(내부 IP:9202)이며, `carrierStats` 배열에 LGU+ 단일 통신사만 반환됨 → 프론트에서는 `carrierStats[0]`만 사용
  - (문서상 구식 정보) 과거 사용되던 `telCd=KT` / `telCd=LGU` 쿼리 파라미터는 더 이상 쓰이지 않음 — 통신사는 호출 호스트 자체로 구분됨

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