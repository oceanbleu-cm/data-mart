-- 퍼널 리포트 "상담하기"(선불+후불) activeUsers/eventCount, 기간 전체(date 없음, 한 행).
-- 치환: {{FROM}}/{{TO}} = YYYYMMDD
SELECT
  COUNT(DISTINCT IF(is_active_user, user_pseudo_id, NULL)) AS activeUsers,
  COUNT(*) AS eventCount
FROM `unsedang.analytics_488612198.events_*`
WHERE _TABLE_SUFFIX BETWEEN '{{FROM}}' AND '{{TO}}'
  AND event_date BETWEEN '{{FROM}}' AND '{{TO}}'
  AND event_name IN ('pre_tel_click', 'post_tel_click')
