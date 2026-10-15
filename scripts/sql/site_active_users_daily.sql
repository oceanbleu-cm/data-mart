-- 사이트 전체 activeUsers, 일별. 소스 필터 없음.
-- 치환: {{FROM}}/{{TO}} = YYYYMMDD (예: 20261013). _TABLE_SUFFIX와 event_date 양쪽에 그대로 쓴다.
SELECT
  FORMAT_DATE('%Y-%m-%d', PARSE_DATE('%Y%m%d', event_date)) AS date,
  COUNT(DISTINCT IF(is_active_user, user_pseudo_id, NULL)) AS activeUsers
FROM `unsedang.analytics_488612198.events_*`
WHERE _TABLE_SUFFIX BETWEEN '{{FROM}}' AND '{{TO}}'
  AND event_date BETWEEN '{{FROM}}' AND '{{TO}}'
GROUP BY 1
ORDER BY 1
