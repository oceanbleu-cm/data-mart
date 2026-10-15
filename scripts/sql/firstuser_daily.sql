-- firstUserSource 원본값별 activeUsers/sessions, 일별. 그룹핑은 파이썬(FIRST_USER_LABEL_TO_GROUP/
-- classify_source)이 담당하므로 여기서는 원본 GA4 표시값 그대로 낸다(docs/bigquery-ga4-mapping.md §2-1
-- 검증 완료 — traffic_source.source가 GA4 API의 firstUserSource에 해당).
-- 치환: {{FROM}}/{{TO}} = YYYYMMDD
SELECT
  FORMAT_DATE('%Y-%m-%d', PARSE_DATE('%Y%m%d', event_date)) AS date,
  COALESCE(traffic_source.source, '(not set)') AS source,
  COUNT(DISTINCT IF(is_active_user, user_pseudo_id, NULL)) AS activeUsers,
  COUNT(DISTINCT CONCAT(user_pseudo_id, '-',
    CAST((SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id') AS STRING)
  )) AS sessions
FROM `unsedang.analytics_488612198.events_*`
WHERE _TABLE_SUFFIX BETWEEN '{{FROM}}' AND '{{TO}}'
  AND event_date BETWEEN '{{FROM}}' AND '{{TO}}'
GROUP BY 1, 2
ORDER BY 1, 2
