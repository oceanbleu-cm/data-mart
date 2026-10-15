-- AI노트 페이지 2종 activeUsers, 기간 전체 dedup(date 없음).
-- 검증: ENGAGEMENT_TOTAL.users와 이 쿼리의 noteInfo 값은 항등(같은 모집단)이어야 한다 —
-- docs/bigquery-ga4-mapping.md §2-2 참고.
-- 치환: {{FROM}}/{{TO}} = YYYYMMDD
SELECT
  path,
  COUNT(DISTINCT IF(is_active_user, user_pseudo_id, NULL)) AS activeUsers
FROM (
  SELECT
    user_pseudo_id, is_active_user,
    REGEXP_EXTRACT(
      (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location'),
      r'^https?://[^/?#]+([^?#]*)'
    ) AS path
  FROM `unsedang.analytics_488612198.events_*`
  WHERE _TABLE_SUFFIX BETWEEN '{{FROM}}' AND '{{TO}}'
    AND event_date BETWEEN '{{FROM}}' AND '{{TO}}'
    AND event_name = 'page_view'
)
WHERE path IN ('/view/ai-note', '/view/ai-note/noteInfo')
GROUP BY 1
ORDER BY 1
