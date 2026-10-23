# GA4 계정
1. unsedang-a3588 #운세당
2. MINDCARE #마인트케어
3. KT_PASS_TODAY - GA4 #kt 투데이
4. PASS운세_신규 - GA4 #lg 투데이
5. web.wisetoday.kr - GA4 #와이즈 외부가입창
7. [SKT/KT/LGU+] app_passhealthcare_2.0 #헬스케어
8. PASS_Cloud #클라우드
9. todaybook  # 오늘의 지식

# 운세당 메인개편 이벤트 정리
개편 섹션	클릭	수정 후 / 주요 값	
메인 배너	배너	main_banner_click (그대로, 경로가 있는 배너는 banner_id가 비어 있음)	
퀵메뉴	메뉴	main_direct_menu (그대로, direct_menu=메뉴 이름)	
최근 본 선생님	상담사	home_recent_csl_click (teacher_name, teacher_status)	
최근 본 선생님	더보기	home_recent_more_click	
찜한 선생님	상담사	home_like_csl_click (teacher_name, teacher_status)	
찜한 선생님	더보기	home_like_more_click	
인기태그	태그	home_tag_click (keyword)	
추천 전화상담	상담사	home_recommend_csl_click (teacher_name, teacher_status, coun_tap=탭)	
재회상담 추천	상담사	home_worry_csl_click (teacher_name, teacher_status, category=subView)	
후기모음	더보기	home_review_more_click	
후기모음	후기	home_review_click (counselor_grade_id)	
후기모음	상담사	home_review_csl_click (teacher_name)	

# DB json 데이터
## 운세당
https://adm.unsedang.com/api/v1/reports/consultation-stats/monthly?baseMonth=2026-09

## 운세당 상담사 매출순위
https://adm.unsedang.com/api/v1/reports/consultation-stats/daily/counselors?date=20261023

## 투데이
KT:
https://admin.wisetoday.kr/api/v1/reports/carrier-subscription-stats/monthly.json?baseMonth=2026-08&telCd=KT
LGU: 
https://admin.wisetoday.kr/api/v1/reports/carrier-subscription-stats/monthly.json?baseMonth=2026-08&telCd=LGU

## 마인드케어
https://admin.firstmindcare.com/api/v1/reports/mindcare-subscription-stats/monthly.json?baseMonth=2026-09

## 오놀의 지식
https://api.todaybook.kr/api/v1/reports/todaybook-subscription-stats/monthly.json