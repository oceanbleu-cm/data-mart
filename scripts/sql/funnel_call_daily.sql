-- 퍼널 리포트 "상담하기"(선불+후불) activeUsers/eventCount, 일별. eventName을 dimension에
-- 넣지 않는다 — 같은 날 pre_tel_click/post_tel_click을 모두 낸 사용자를 중복 집계하지 않기 위함.
-- 검증: 2026-10-13 BQ 73/265 vs 기존 HTML DAILY_CALL 73/265 — 완전 일치(docs/bigquery-ga4-mapping.md §2-2).
-- 치환: {{FROM}}/{{TO}} = YYYYMMDD
SELECT
  FORMAT_DATE('%Y-%m-%d', PARSE_DATE('%Y%m%d', event_date)) AS date,
  COUNT(DISTINCT IF(is_active_user, user_pseudo_id, NULL)) AS activeUsers,
  COUNT(*) AS eventCount
FROM `unsedang.analytics_488612198.events_*`
WHERE _TABLE_SUFFIX BETWEEN '{{FROM}}' AND '{{TO}}'
  AND event_date BETWEEN '{{FROM}}' AND '{{TO}}'
  AND event_name IN ('pre_tel_click', 'post_tel_click')
GROUP BY 1
ORDER BY 1
