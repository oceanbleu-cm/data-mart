# Claude 클라우드 라우틴 생성 가이드

이 문서는 `/update-ga4-unsedang-daily` 라우틴을 만들면서 겪은 실전 노하우를 정리한
것입니다. 다음에 비슷한(정기 실행) 라우틴을 만들 때 참고하세요.

---

## 1. 사전 조건 — GitHub 저장소를 쓰는 라우틴은 2단계 권한이 필요

로컬에서 `gh auth login`으로 GitHub에 로그인돼 있어도 클라우드 라우틴과는 **완전히
별개**입니다. 아래 두 단계가 모두 필요합니다.

1. **claude.ai 계정-GitHub 연결** (최초 1회): https://claude.ai/code/onboarding?magic=github-app-setup
2. **해당 저장소에 대한 App 권한 부여**: https://github.com/settings/installations →
   Claude 앱 옆 **Configure** → "Repository access"에서 대상 저장소를 명시적으로 추가
   (또는 "All repositories"로 변경)

**private 저장소는 기본적으로 막혀 있습니다.** 아래 에러가 뜨면 이 단계부터 의심하세요.

| 에러 | 원인 | 해결 |
|---|---|---|
| `401 Connect your GitHub account before saving a routine...` | 1단계(계정 연결) 미완료 | 온보딩 링크로 계정 연결 |
| `403 You don't have access to a repository this routine uses` | 2단계(저장소별 App 권한) 미완료 | installations 설정에서 저장소 추가 |

두 단계를 마친 뒤에는 **같은 요청을 그대로 재시도**하면 됩니다 — 별도 파라미터 변경 불필요.

---

## 2. 항상 `Skill: schedule`부터 호출할 것

커넥터 UUID·환경(environment) ID는 **계정 상태에 따라 바뀔 수 있어 이 문서에
하드코딩하지 않습니다.** 라우틴을 만들 때마다 `schedule` 스킬을 먼저 불러서 그 시점의
최신 값(연결된 MCP 커넥터 목록, 사용 가능한 environment_id)을 받아 쓰세요.

`RemoteTrigger` 툴 자체는 기본 목록에 안 보일 수 있으니 `ToolSearch select:RemoteTrigger`로
먼저 로드합니다.

---

## 3. `create` body 구조 요약

```json
{
  "name": "ROUTINE_NAME",
  "cron_expression": "0 4 * * *",
  "enabled": true,
  "job_config": {
    "ccr": {
      "environment_id": "ENV_ID",
      "session_context": {
        "model": "claude-sonnet-5",
        "sources": [{ "git_repository": { "url": "https://github.com/ORG/REPO" } }],
        "allowed_tools": ["Bash", "Read", "Write", "Edit", "Glob", "Grep"]
      },
      "events": [{
        "data": {
          "uuid": "<매번 새로 생성하는 lowercase v4 uuid>",
          "session_id": "",
          "type": "user",
          "parent_tool_use_id": null,
          "message": { "role": "user", "content": "PROMPT" }
        }
      }]
    }
  },
  "mcp_connections": [
    { "connector_uuid": "...", "name": "...", "url": "..." }
  ]
}
```

**함정**: `mcp_connections`는 `job_config` **안이 아니라 body의 최상위 필드**입니다.
`job_config.ccr` 안에 넣으면 스키마 예제만 보고 착각하기 쉬우니 주의.

1회성 실행은 `cron_expression` 대신 `run_once_at`(RFC3339 UTC, 미래 시각)을 씁니다.

---

## 4. cron은 항상 UTC — 타임존 변환 필수

- 사용자 타임존: **Asia/Seoul (UTC+9, DST 없음)**
- 변환 예: 13:00 KST = 04:00 UTC → `"0 4 * * *"`
- **항상 변환값을 사용자에게 확인**하고 진행 (예: "13시 KST = 04:00 UTC, 이렇게 만들까요?")
- **최소 실행 간격은 1시간** — `*/30 * * * *` 같은 것은 거부됨

---

## 5. 무인 실행 프롬프트 작성 원칙

클라우드 세션은 **매번 완전히 무맥락 상태로 시작**합니다. 프롬프트는 그 자체로
완결돼야 합니다.

- 대상 저장소에 이미 커스텀 슬래시 커맨드(예: `.claude/commands/update-ga4-unsedang.md`)가
  있다면, 프롬프트에서 통째로 재설명하지 말고 **"그 문서를 따라 실행하라"고 참조**시키는
  게 짧고 안전합니다.
- **"사용자 확인을 기다리지 말고 끝까지 자동으로 진행하라"**는 문구를 명시적으로
  넣어야 합니다 — 대화형 세션 기본 동작(중간에 확인받기)과 다릅니다.
- **커밋·푸시는 명시적으로 지시해야 합니다.** 이 프로젝트의 대화형 세션 기본값은
  "커밋은 사용자가 명시적으로 요청할 때만"이지만, 무인 라우틴은 그 자체가 "변경사항을
  반영해라"는 지시이므로 프롬프트 안에서 이 기본값을 명시적으로 뒤집어야 합니다
  (예: "변경된 파일이 있으면 git add/commit/push까지 반드시 완료하라").
- 실패 시 동작(예: 검증 실패 시 우회하지 말고 원인만 남기고 커밋 없이 종료)도 프롬프트에
  명시해두면 라우틴이 조용히 잘못된 데이터를 밀어넣는 사고를 막을 수 있습니다.

---

## 6. 디버깅

- `list_runs` (trigger_id) → 최근 실행 세션 목록
- `get_run_log` (session_id) → 한 실행의 상세 로그(툴 호출, 에러, 최종 결과)
- 목록이 비어있다고 "한 번도 안 돌았다"고 단정하지 말 것 — 라우틴이 일시정지됐거나,
  사전 체크(저장소 접근 등)에서 막혀 세션 자체가 안 만들어진 경우도 목록에 안 나타남.
  이럴 땐 `get`으로 라우틴 자체 상태(`enabled`, `next_run_at`)를 확인.
- **라우틴 삭제는 API로 불가능** — https://claude.ai/code/routines 에서 직접 삭제.

---

## 7. 실제 성공 사례

**`update-ga4-unsedang-daily`** (`trig_01SJTJqrLY6ynjnEQxERNY7n`)
- 목적: `html/ga4-funnel-unsedang.html`을 매일 증분 갱신 (`.claude/commands/update-ga4-unsedang.md` 참조 실행)
- 일정: 매일 04:00 UTC = 13:00 KST
- 저장소: `cfguyk7/bleu-data-mart`
- MCP 연결: Supermetrics Marketing Analytics
- 생성 과정에서 §1의 두 에러(401 → GitHub 계정 연결, 403 → 저장소별 App 권한)를 순서대로
  겪고 해결한 뒤 3번째 시도에서 성공
