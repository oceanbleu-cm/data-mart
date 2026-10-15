-- AI노트 상세(/view/ai-note/noteInfo) 참여시간 합계(초)/activeUsers, 일별.
-- totalEngagementDuration은 msec 합계를 1000으로 나눈 초 단위 정수(HTML 저장 단위에 맞춤).
-- 검증: 2026-10-13 BQ [7453,26] vs 기존 HTML DAILY_ENGAGEMENT [7336,25] — 오차 1.6%/절대1
-- (docs/bigquery-ga4-mapping.md §2-2, 허용범위 내).
-- 치환: {{FROM}}/{{TO}} = YYYYMMDD
SELECT
  FORMAT_DATE('%Y-%m-%d', PARSE_DATE('%Y%m%d', event_date)) AS date,
  CAST(ROUND(SUM(eng_ms) / 1000) AS INT64) AS totalEngagementDuration,
  COUNT(DISTINCT IF(is_active_user, user_pseudo_id, NULL)) AS activeUsers
FROM (
  SELECT
    event_date, user_pseudo_id, is_active_user,
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
GROUP BY 1
ORDER BY 1
