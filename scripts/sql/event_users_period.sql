-- event_users_daily.sql의 기간 전체 dedup 버전(date 없음, 한 행). {{EVENT_PREDICATE}} 동일.
-- 치환: {{FROM}}/{{TO}} = YYYYMMDD, {{EVENT_PREDICATE}}
SELECT
  COUNT(DISTINCT IF(is_active_user, user_pseudo_id, NULL)) AS activeUsers
FROM `unsedang.analytics_488612198.events_*`
WHERE _TABLE_SUFFIX BETWEEN '{{FROM}}' AND '{{TO}}'
  AND event_date BETWEEN '{{FROM}}' AND '{{TO}}'
  AND {{EVENT_PREDICATE}}
