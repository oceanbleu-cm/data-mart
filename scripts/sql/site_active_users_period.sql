-- 사이트 전체 activeUsers, 기간 전체 dedup(한 행). 비집계 지표라 date를 빼고 통째로 재조회.
-- 치환: {{FROM}}/{{TO}} = YYYYMMDD
SELECT
  COUNT(DISTINCT IF(is_active_user, user_pseudo_id, NULL)) AS activeUsers
FROM `unsedang.analytics_488612198.events_*`
WHERE _TABLE_SUFFIX BETWEEN '{{FROM}}' AND '{{TO}}'
  AND event_date BETWEEN '{{FROM}}' AND '{{TO}}'
