-- AI노트 KPI 리포트: 단일 이벤트 조건의 activeUsers만 필요한 지표용 범용 쿼리(call/pretel/recoclick).
-- eventCount가 필요 없는 경우에만 쓴다(필요하면 funnel_call_*.sql처럼 eventCount 포함 버전을 쓸 것).
-- 치환: {{FROM}}/{{TO}} = YYYYMMDD, {{EVENT_PREDICATE}} = 커맨드 .md에 고정된 조건 중 하나:
--   call:      event_name IN ('pre_tel_click', 'post_tel_click')
--   pretel:    event_name = 'pre_tel_click'
--   recoclick: REGEXP_CONTAINS(event_name, r'callnote_reco_click')
SELECT
  FORMAT_DATE('%Y-%m-%d', PARSE_DATE('%Y%m%d', event_date)) AS date,
  COUNT(DISTINCT IF(is_active_user, user_pseudo_id, NULL)) AS activeUsers
FROM `unsedang.analytics_488612198.events_*`
WHERE _TABLE_SUFFIX BETWEEN '{{FROM}}' AND '{{TO}}'
  AND event_date BETWEEN '{{FROM}}' AND '{{TO}}'
  AND {{EVENT_PREDICATE}}
GROUP BY 1
ORDER BY 1
