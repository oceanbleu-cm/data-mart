-- AI노트 추적 이벤트 7종(SUBEVENT_KEYS) activeUsers, 일별. 희소 저장 방식 — 결측 날짜/이벤트는
-- 행 자체가 없는 게 정상(update_ga4_ainote_kpi_unsedang.py 참고).
-- 치환: {{FROM}}/{{TO}} = YYYYMMDD
SELECT
  FORMAT_DATE('%Y-%m-%d', PARSE_DATE('%Y%m%d', event_date)) AS date,
  event_name AS eventName,
  COUNT(DISTINCT IF(is_active_user, user_pseudo_id, NULL)) AS activeUsers
FROM `unsedang.analytics_488612198.events_*`
WHERE _TABLE_SUFFIX BETWEEN '{{FROM}}' AND '{{TO}}'
  AND event_date BETWEEN '{{FROM}}' AND '{{TO}}'
  AND event_name IN (
    'ai-note-agree-pop', 'ai-note-agree-click', 'ai-note-cancel-click',
    'ai-note-review-skip', 'ai-note-review-next', 'ai-note-review-submit',
    'ai-note-councel-click'
  )
GROUP BY 1, 2
ORDER BY 1, 2
