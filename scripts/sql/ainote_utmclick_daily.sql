-- AI노트 알림톡 "바로가기" UTM 클릭 activeUsers, 일별. 세션 스코프 필터
-- (sessionSource=kakao_alimtalk AND sessionMedium=push AND sessionCampaignName=callnote_created)이므로
-- collected_traffic_source를 세션 단위로 귀속한다(naver-powerlink.md에서 검증된 패턴,
-- ARRAY_AGG(... IGNORE NULLS ORDER BY event_timestamp LIMIT 1)).
-- 검증: 2026-10-13 BQ 16 vs 기존 HTML DAILY_UTM_CLICK 16 — 완전 일치(docs/bigquery-ga4-mapping.md §2-2/§2-4).
-- 치환: {{FROM}}/{{TO}} = YYYYMMDD
WITH ev AS (
  SELECT
    event_date, event_timestamp, user_pseudo_id, is_active_user,
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
  SELECT DISTINCT e.event_date, e.user_pseudo_id, e.is_active_user
  FROM ev e
  JOIN sess s USING (user_pseudo_id, sid)
  WHERE s.src = 'kakao_alimtalk' AND s.med = 'push' AND s.cmp = 'callnote_created'
)
SELECT
  FORMAT_DATE('%Y-%m-%d', PARSE_DATE('%Y%m%d', event_date)) AS date,
  COUNT(DISTINCT IF(is_active_user, user_pseudo_id, NULL)) AS activeUsers
FROM matched
GROUP BY 1
ORDER BY 1
