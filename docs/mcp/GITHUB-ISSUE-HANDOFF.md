# GitHub Issue Handoff — LSS-MCP-G0001

## Suggested title

`[LSS-MCP-G0001][DEV/NOT-RELEASED] PostgreSQL·Alembic·ERP REST backend hand-back 요청`

## Suggested labels

`backend`, `mcp`, `security`, `development`

## Issue body

### 목적

`khlee-add-mcp` 브랜치의 DB 없는 MCP 로컬 검증 패키지를 기준으로,
메인 개발자 소유의 PostgreSQL·Alembic·token/scope·ERP REST API 작업과
재현 가능한 evidence hand-back을 요청합니다.

이 이슈는 개발 업무 전달용입니다. 현재 상태는
`DEVELOPMENT/NOT-RELEASED`입니다. 메인 개발자의 별도 backend 작업
branch 생성이나 그 작업 branch로의 병합은 허용하지만, `origin/main`
병합·실제 서버 배포·실제 ERP write 활성화를 승인하지 않습니다.

현재 MCP 범위는 타임시트 중심 7개 도구와 5개 REST endpoint입니다.
AI 호스트는 개인 업무일지를 로컬에서 읽고 최소 구조화 사실만 MCP에
전달하며, MCP는 기존 행을 보존한 병합 초안·일별/주간 합계·예외 질문을
만듭니다. 개인 업무일지 원문이나 경로는 ERP로 전달하지 않습니다.
ERP의 모든 API를 MCP로 공개하는 작업이 아니며, 추가 기능은 별도
scope·contract·위협 검토·테스트 Goal이 필요합니다.

### 기준점

- branch: `khlee-add-mcp`
- verified implementation checkpoint: push 후 `git rev-parse HEAD` 결과 사용
- active Goal: `LSS-MCP-G0001`
- release state: `DEVELOPMENT/NOT-RELEASED`
- local database: 없음
- PostgreSQL/Alembic/실제 API/canary/rollback: `NOT-RUN`

### 먼저 읽을 문서

1. `docs/mcp/AI-MAIN-DEVELOPER-ENTRYPOINT.md`
2. `docs/handoffs/2026-07-25-lss-erp-mcp-backend-db-token-handoff.md`
3. `docs/superpowers/specs/2026-07-25-lss-erp-ai-timesheet-automation-design.md`
4. `docs/superpowers/plans/2026-07-25-lss-erp-ai-timesheet-automation.md`
5. `docs/mcp/API-CONTRACT.md`
6. `docs/mcp/AI-SAFETY-BASELINE.md`
7. `docs/mcp/APPLY-AND-ROLLBACK.md`
8. `docs/mcp/EVIDENCE-HAND-BACK.md`
9. `docs/mcp/LOCAL-VERIFICATION.md`

### 메인 개발자 작업

- [ ] 작업 branch와 정확한 backend commit SHA 기록
- [ ] production이 아님을 증명할 PostgreSQL 16 test lane 식별
- [ ] employee/week 및 parking duplicate preflight 실행·건수 반환
- [ ] Alembic revision 작성, upgrade와 downgrade 재현
- [ ] API token hash·expiry·revocation·client/resource/scope default-deny 구현
- [ ] token identity를 기존 `AuthContext`로 연결
- [ ] token에서 검증한 `user_id`·`employee_id`만 사용하고
      client가 identity·status를 선택하지 못함을 테스트
- [ ] 아래 최소 REST 계약 구현
  - `GET /api/auth/me` — `mcp:discover`
  - `GET /api/timesheets/week` — `timesheet:read:self`
  - `GET /api/timesheets/entry-context` — `timesheet:read:self`
  - `GET /api/timesheets/projects` — `timesheet:read:self`
  - `POST /api/timesheets/mcp-draft` —
    `timesheet:write:self:draft`
- [ ] self-only·draft-only·protected-state·expected-version 검증
- [ ] 실행·영업·공통·연차 expanded DTO를 기존 요일별 row로 무손실 변환
- [ ] `labor_type`은 AI 입력이 아니라 token 소유 직원에서 서버가 결정
- [ ] frontend/backend 작업유형 목록 차이(`영업 > SHOP작업` 포함) 해소
- [ ] entry-context의 일별 기준시간과 기존 UI 합계가 일치함을 테스트
- [ ] 업무일지에서 언급하지 않은 기존 row가 보존됨을 실제 API에서 검증
- [ ] `(employee_id, week_start)` PostgreSQL unique 보장
- [ ] idempotency key + request hash + audit + mutation 단일 transaction 보장
- [ ] success 및 401/403/404/409/422/429/5xx contract/security 테스트
- [ ] 기존 `/api/mcp` read contract와 기존 ERP UI 회귀 테스트
- [ ] development OpenAPI 산출물과 SHA-256 반환
- [ ] credential 없는 development API base URL 반환
- [ ] Windows Credential Manager service/target 이름만 반환
- [ ] token revoke `401`, migration/backend rollback, legacy UI smoke 재현

### 필수 hand-back

`docs/mcp/EVIDENCE-HAND-BACK.md` 형식으로 다음을 반환해 주세요.

- backend commit SHA
- non-production PostgreSQL test-lane 증거
- Alembic before/applied/rollback revision
- OpenAPI SHA-256
- dependency audit 명령과 출력
- backend contract/security/PostgreSQL/migration/UI 테스트 명령과 출력
- duplicate preflight 건수
- credential-free development API base URL
- Credential Manager service/target 이름
- rollback 명령·출력·최종 data/migration 상태
- 남은 blocker와 `UNKNOWN`

`NONE`, `NOT-RUN`, `UNKNOWN`을 추정값으로 바꾸지 마세요.

### 절대 금지

- MCP 프로세스에 DB account, `DATABASE_URL`, `SECRET_KEY`, backend import 제공
- token, authorization header, connection string, raw request body, 개인 vault
  path를 Git·Markdown·이슈·로그·스크린샷에 기록
- SQLite-only 결과로 PostgreSQL migration을 PASS 처리
- 제출·승인·반려 상태를 MCP로 변경
- 이 branch 존재만으로 `origin/main` 병합·배포·실제 write 활성화

### 현재 로컬 evidence

- pytest: `108 passed`
- MCP Python SDK stdio initialize/list/call: PASS
- MCP Python SDK `tools/list`: 7개 도구와 annotations PASS
- external MCP Inspector `tools/list`: 정확히 7개 도구 PASS
- compileall: PASS
- banned runtime references: 0
- Python dependency audit: 알려진 취약점 0
- Mermaid: 13/13 실제 렌더 PASS
- secret pattern scan: 0
- frontend build: 3,841 modules PASS
- 이번 checkpoint 자체 review: 발견된 중요 결함 5건 수정 후 회귀 테스트 PASS
- 이번 checkpoint 독립 review: `NOT-RUN`; main developer가 별도 backend branch에서 재검토

위 결과는 DB 없는 로컬 MCP lane만 증명합니다. 실제 Credential Manager,
PostgreSQL, deployed API, read-only integration, one-user canary, rollback은
아직 증명하지 않습니다.

### 완료 조건

- [ ] hand-back 필수 항목이 명령 출력과 함께 제출됨
- [ ] G0001 backend dependency/contract/security/PostgreSQL 증거 수락
- [ ] real API read-only 검증을 시작할 수 있는 credential-free endpoint 제공
- [ ] blocker와 `UNKNOWN`이 명시됨

G0009 `COMPLETE/PASS`와 사용자 별도 승인 전에는 `origin/main` release
merge, deployment, real ERP write activation을 진행하지 않습니다.
