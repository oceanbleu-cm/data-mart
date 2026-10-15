-- 퍼널 리포트 페이지 5종 activeUsers, 기간 전체 dedup(date 없음). sessions는 기간합계에서
-- 쓰지 않는다(PAGE_TOTALS 스키마는 activeUsers만).
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
WHERE path IN ('/view/home', '/view/csl', '/view/csl/cslInfo', '/view/content', '/view/csl/totalRatingComment')
GROUP BY 1
ORDER BY 1
