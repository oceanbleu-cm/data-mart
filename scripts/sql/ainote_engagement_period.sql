-- AI노트 상세 참여시간 합계(초)/activeUsers, 기간 전체(date 없음, 한 행).
-- 치환: {{FROM}}/{{TO}} = YYYYMMDD
SELECT
  CAST(ROUND(SUM(eng_ms) / 1000) AS INT64) AS totalEngagementDuration,
  COUNT(DISTINCT IF(is_active_user, user_pseudo_id, NULL)) AS activeUsers
FROM (
  SELECT
    user_pseudo_id, is_active_user,
    COALESCE((SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'engagement_time_msec'), 0) AS eng_ms,
    REGEXP_EXTRACT(
      (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location'),
      r'^https?://[^/?#]+([^?#]*)'
    ) AS path
  FROM `unsedang.analytics_488612198.events_*`
  WHERE _TABLE_SUFFIX BETWEEN '{{FROM}}' AND '{{TO}}'
    AND event_date BETWEEN '{{FROM}}' AND '{{TO}}'
)
WHERE path = '/view/ai-note/noteInfo'
