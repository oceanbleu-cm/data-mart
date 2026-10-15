-- AI노트 알림톡 UTM 클릭 activeUsers, 기간 전체(date 없음, 한 행). 세션 귀속 로직은
-- ainote_utmclick_daily.sql과 동일.
-- 치환: {{FROM}}/{{TO}} = YYYYMMDD
WITH ev AS (
  SELECT
    user_pseudo_id, event_timestamp, is_active_user,
    (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id') AS sid,
    collected_traffic_source.manual_source AS cts_source,
    collected_traffic_source.manual_medium AS cts_medium,
    collected_traffic_source.manual_campaign_name AS cts_campaign
  FROM `unsedang.analytics_488612198.events_*`
  WHERE _TABLE_SUFFIX BETWEEN '{{FROM}}' AND '{{TO}}'
    AND event_date BETWEEN '{{FROM}}' AND '{{TO}}'
),
sess AS (
  SELECT
    user_pseudo_id, sid,
    ARRAY_AGG(cts_source   IGNORE NULLS ORDER BY event_timestamp LIMIT 1)[SAFE_OFFSET(0)] AS src,
    ARRAY_AGG(cts_medium   IGNORE NULLS ORDER BY event_timestamp LIMIT 1)[SAFE_OFFSET(0)] AS med,
    ARRAY_AGG(cts_campaign IGNORE NULLS ORDER BY event_timestamp LIMIT 1)[SAFE_OFFSET(0)] AS cmp
  FROM ev
  GROUP BY 1, 2
),
matched AS (
  SELECT DISTINCT e.user_pseudo_id, e.is_active_user
  FROM ev e
  JOIN sess s USING (user_pseudo_id, sid)
  WHERE s.src = 'kakao_alimtalk' AND s.med = 'push' AND s.cmp = 'callnote_created'
)
SELECT
  COUNT(DISTINCT IF(is_active_user, user_pseudo_id, NULL)) AS activeUsers
FROM matched
