# 출처 및 로컬 변경 사항

- **Upstream**: https://github.com/SNLabat/SEO-GEO-AEO-Skill
- **고정 커밋**: `a2c8769b85813912b2b01cd12c3484f061b439fc` (2026-09-18 조회 기준, README/SKILL.md 2파일뿐)
- 원본은 플러그인이 아니라 Cowork 데스크톱 앱용 ZIP 배포 단일 스킬. 이 프로젝트에는
  `.claude/skills/seo-geo-aeo/SKILL.md`로 프로젝트 스코프 설치했다.

## 로컬 변경 3건 (원본 대비)

1. **인트로 문장**: "produce a polished downloadable report as both a Word document (.docx) and PDF"
   → "produce a polished self-contained HTML report (viewable in a browser and printable to PDF)".
2. **오타 수정**: GEO 섹션의 "Sameás / brand entity links" → `sameAs / brand entity links`
   (schema.org 속성명이므로 오타를 두면 분석 지시가 흐려짐).
3. **Step 5 전면 교체**: 원본은 `docx` npm 패키지 + Cowork 전용 경로
   (`/sessions/wizardly-charming-thompson/mnt/outputs/`, `validate.py`, `soffice.py`,
   `present_files`, `computer://` 링크)에 의존해 이 환경(로컬 macOS, LibreOffice·pandoc 미설치)에서는
   실행 불가. 단일 파일 HTML 리포트 생성으로 교체했다:
   - 출력 경로: `html/seo-audit-{domain}-{YYYYMMDD}.html`
   - 라이트/다크 테마 CSS 변수 3단 정의(이 프로젝트의 `html/db-data-*.html` 관행 계승)
   - `@media print`로 브라우저 인쇄 → PDF 저장 경로 확보
   - 원본의 색상 팔레트·리포트 구조(커버/Executive Summary/Pages Audited/SEO·GEO·AEO 분석/
     Priority Recommendations/What's Working Well/Glossary)는 그대로 유지, DOCX 표 문법만
     HTML 표로 옮김
4. Step 1~4, Step 6, "Important principles"(문구 1건 제외)는 원본 그대로.

## 갱신 확인 방법

upstream이 바뀌었는지 확인하려면:

```bash
curl -sL https://raw.githubusercontent.com/SNLabat/SEO-GEO-AEO-Skill/main/SKILL.md \
  | diff - <(curl -sL https://raw.githubusercontent.com/SNLabat/SEO-GEO-AEO-Skill/a2c8769b85813912b2b01cd12c3484f061b439fc/SKILL.md)
```

Step 1~4·Step 6·principles가 바뀌었으면 그 부분만 반영하고, Step 5는 위 로컬 버전을 유지할 것
(원본 Step 5를 그대로 덮어쓰면 다시 깨진다).
