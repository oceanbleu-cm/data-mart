-- 노트 상세(/view/ai-note/noteInfo) 스크롤 90% 도달 — 기간 전체 activeUsers(비집계 지표라
-- 일별 합산이 아니라 전체 기간 재조회 필수). 치환: {{FROM}}/{{TO}} = YYYYMMDD
SELECT
  COUNT(DISTINCT IF(is_active_user, user_pseudo_id, NULL)) AS activeUsers
FROM (
  SELECT
    user_pseudo_id, is_active_user,
    (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'percent_scrolled') AS percent_scrolled,
    REGEXP_EXTRACT(
      (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location'),
      r'^https?://[^/?#]+([^?#]*)'
    ) AS path
  FROM `unsedang.analytics_488612198.events_*`
  WHERE _TABLE_SUFFIX BETWEEN '{{FROM}}' AND '{{TO}}'
    AND event_date BETWEEN '{{FROM}}' AND '{{TO}}'
    AND event_name = 'scroll'
)
WHERE percent_scrolled = 90
  AND path = '/view/ai-note/noteInfo'
