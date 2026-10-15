-- AI노트 추적 이벤트 7종 activeUsers, 기간 전체 dedup(date 없음).
-- 치환: {{FROM}}/{{TO}} = YYYYMMDD
SELECT
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
GROUP BY 1
ORDER BY 1
