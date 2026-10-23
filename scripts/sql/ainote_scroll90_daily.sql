-- 노트 상세(/view/ai-note/noteInfo) 스크롤 90% 도달 — GA4 Enhanced Measurement가 자동 수집하는
-- scroll 이벤트(percent_scrolled=90)의 activeUsers, 일별.
-- 치환: {{FROM}}/{{TO}} = YYYYMMDD
SELECT
  FORMAT_DATE('%Y-%m-%d', PARSE_DATE('%Y%m%d', event_date)) AS date,
  COUNT(DISTINCT IF(is_active_user, user_pseudo_id, NULL)) AS activeUsers
FROM (
  SELECT
    event_date, user_pseudo_id, is_active_user,
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
GROUP BY 1
ORDER BY 1
