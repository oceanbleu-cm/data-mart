-- 퍼널 리포트 페이지 5종 activeUsers/sessions, 일별. page_view 이벤트만 신뢰
-- (클릭 이벤트의 page_location은 SPA 가상 라우팅 탓에 신뢰 불가 — docs/ga4-term.md 및
-- reference-bigquery-ga4-export 메모리 참고). PAGE_PATH_TO_KEY(update_ga4_unsedang.py)와
-- 동일한 5개 경로 — 새 경로가 필요하면 이 파일과 PAGE_PATH_TO_KEY를 사람이 함께 갱신한다.
-- 치환: {{FROM}}/{{TO}} = YYYYMMDD
SELECT
  FORMAT_DATE('%Y-%m-%d', PARSE_DATE('%Y%m%d', event_date)) AS date,
  path,
  COUNT(DISTINCT IF(is_active_user, user_pseudo_id, NULL)) AS activeUsers,
  COUNT(DISTINCT CONCAT(user_pseudo_id, '-', CAST(sid AS STRING))) AS sessions
FROM (
  SELECT
    event_date, user_pseudo_id, is_active_user,
    (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id') AS sid,
    REGEXP_EXTRACT(
      (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location'),
      r'^https?://[^/?#]+([^?#]*)'
    ) AS path
  FROM `unsedang.analytics_488612198.events_*`
  WHERE _TABLE_SUFFIX BETWEEN '{{FROM}}' AND '{{TO}}'
    AND event_date BETWEEN '{{FROM}}' AND '{{TO}}'
    AND event_name = 'page_view'
)
WHERE path IN ('/view/home', '/view/csl', '/view/csl/cslInfo', '/view/content', '/view/csl/totalRatingComment')
GROUP BY 1, 2
ORDER BY 1, 2
