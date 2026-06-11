# 0001. Claude Code 프로젝트 자동화 도구 선정

- 날짜: 2026-06-11
- 상태: 채택됨

## 배경 (Context)

claude-automation-recommender 분석 결과(hooks, 프로젝트 스킬, 전담 리뷰 에이전트, CI, Docker MCP)를 구현하면서 네 가지 채택 결정이 있었다. 이 ADR은 "채택 시 비교 선행 + 문서화" 규칙 도입에 따라 같은 날 소급 작성되었다.

## 결정 1: 포맷/린트 자동 집행 — `.claude/settings.json` hook 채택

선택 기준: 결정론적 실행(모델 재량 배제), 피드백 시점, 외부 의존성, 차단 능력(.env 보호 겸용).

| 기준 | settings.json hook ✅ | hookify rule | CLAUDE.md 지시 | pre-commit |
|---|---|---|---|---|
| 결정론적 실행 | O (하니스가 실행) | O | X (모델이 기억해야 함) | O |
| 피드백 시점 | 편집 직후 | 편집 직후 | 비보장 | 커밋 시점 (늦음) |
| 외부 의존성 | 없음 (jq, ruff만) | hookify 플러그인 | 없음 | pre-commit 패키지 |
| 팀 공유 (repo 체크인) | O | O | O | O |
| 편집 차단 (.env 보호) | O (PreToolUse exit 2) | O | X | X (편집 자체는 못 막음) |

**선택 이유**: 편집 직후 집행 + 플러그인 의존 없음 + `.env` 차단까지 한 메커니즘으로 해결된다. hookify는 내부적으로 동일한 hook을 생성하므로 표준 포맷을 직접 작성하는 쪽이 이식성이 높다. pre-commit은 Claude의 편집 루프에 피드백이 늦고 `.env` 편집 자체를 막지 못한다.

## 결정 2: 백엔드 계약 문서 위치 — 프로젝트 CLAUDE.md 채택

선택 기준: 로드 보장, 유지보수 도구, 사람 가독성, 토큰 비용.

| 기준 | CLAUDE.md ✅ | Claude 전용 스킬 (user-invocable: false) | README 확장 |
|---|---|---|---|
| 로드 보장 | 매 세션 자동 | 모델이 선택 로드 (누락 가능) | 자동 로드 안 됨 |
| 유지보수 | claude-md-management 플러그인 보유 | 수동 | 수동 |
| 사람도 읽는가 | O | 사실상 X | O |
| 토큰 비용 | 매 세션 고정 (~40줄) | 호출 시만 | 0 |

**선택 이유**: 백엔드 계약 위반이 반복 버그의 원인이었으므로(공유 인스턴스 race, reference 무시, 늦은 키 검증) "가끔 로드"가 아니라 "항상 로드"가 필요하다. 고정 토큰 비용은 40줄 수준으로 수용 가능.

## 결정 3: CI — GitHub Actions (기본값 채택)

GitHub 호스팅 + 무료 티어 + 추가 인프라 불요로 사실상 표준이라 풀 비교를 생략했다 (전역 CLAUDE.md의 trivial 선택 규칙).

유의미한 세부 결정 — `ruff format --check`를 CI에서 **제외**: 현재 10개 파일이 미포맷 상태라 포함 시 즉시 실패하고, 오픈된 PR #1 브랜치에서 일괄 재포맷하면 PR이 오염되기 때문. `pytest`(66개)와 `ruff check`는 로컬 검증 후 포함.

## 결정 4: Docker MCP — 미채택

| 기준 | 공식 플러그인 | 커뮤니티 MCP 서버 | Bash `docker compose` (현행) ✅ |
|---|---|---|---|
| 존재/신뢰성 | 마켓플레이스에 없음 (설치 시도로 확인) | 미검증 서드파티 | 이미 동작 |
| 도입 비용 | - | `claude mcp add` + 코드 검증 필요 | 0 |
| 기능 격차 | - | 로그/상태 조회 도구화 | Bash로 동일 작업 가능 |

**선택 이유**: 추천 단계의 웹 검색 결과와 달리 공식 마켓플레이스에 docker 플러그인이 없음을 `claude plugin install` 시도와 마켓플레이스 manifest 검색으로 확인했다. 미검증 커뮤니티 서버를 임의 설치하지 않고 현행(Bash) 유지.

## 결과 및 재평가 조건 (Consequences)

- 감수하는 것: format 일괄 커밋 전까지, 미포맷 파일을 편집하면 hook이 파일 전체를 재포맷해 diff가 커질 수 있음.
- 재평가 트리거:
  - main에서 일회성 `ruff format .` 커밋 후 → CI에 `ruff format --check` 추가 (결정 3).
  - 공식 docker 플러그인 출시 → 결정 4 재검토.
  - Docker Desktop MCP Toolkit을 GUI로 연결하는 경우 → 결정 4 대체.
