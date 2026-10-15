-- firstUserSource 원본값별 activeUsers/sessions, 기간 전체 dedup(date 없음).
-- 치환: {{FROM}}/{{TO}} = YYYYMMDD
SELECT
  COALESCE(traffic_source.source, '(not set)') AS source,
  COUNT(DISTINCT IF(is_active_user, user_pseudo_id, NULL)) AS activeUsers,
  COUNT(DISTINCT CONCAT(user_pseudo_id, '-',
    CAST((SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id') AS STRING)
  )) AS sessions
FROM `unsedang.analytics_488612198.events_*`
WHERE _TABLE_SUFFIX BETWEEN '{{FROM}}' AND '{{TO}}'
  AND event_date BETWEEN '{{FROM}}' AND '{{TO}}'
GROUP BY 1
ORDER BY 1
