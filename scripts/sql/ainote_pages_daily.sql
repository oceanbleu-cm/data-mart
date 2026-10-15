-- AI노트 페이지 2종(aiNote/noteInfo) activeUsers, 일별. page_view만 신뢰.
-- PAGE_PATH_TO_KEY(update_ga4_ainote_kpi_unsedang.py)와 동일 2개 경로 — 새 경로 추가 시
-- 이 파일을 사람이 함께 갱신한다.
-- 치환: {{FROM}}/{{TO}} = YYYYMMDD
SELECT
  FORMAT_DATE('%Y-%m-%d', PARSE_DATE('%Y%m%d', event_date)) AS date,
  path,
  COUNT(DISTINCT IF(is_active_user, user_pseudo_id, NULL)) AS activeUsers
FROM (
  SELECT
    event_date, user_pseudo_id, is_active_user,
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
GROUP BY 1, 2
ORDER BY 1, 2
