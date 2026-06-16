# 0004. Codex agent surface redesign

- 날짜: 2026-06-13
- 상태: 채택됨

## 배경 (Context)

`part4`에는 Claude Code용 `.claude/skills/new-backend`, `.claude/agents/backend-contract-reviewer.md`, `.claude/settings.json` hook이 있다. Codex에서 같은 의도를 쓰려면 Claude `tools`/`model` metadata와 hook semantics를 그대로 복사하지 말고 Codex skill, custom agent, project hook으로 나눠야 한다.

## 선택 기준 (Criteria)

- 높음: `.env` 직접 편집과 live provider 호출을 막는 guardrail.
- 높음: `new-backend`와 `backend-contract-reviewer`가 Codex에서 명확히 trigger되는가.
- 중: Claude `model: sonnet`과 `tools` metadata를 Codex 권한으로 오해하지 않는가.
- 중: backend contract review가 read-only로 유지되는가.
- 낮음: 자동 변환량을 최대화하는가.

## 후보 비교 (Comparison)

| 기준 | A. full migrator 실행 | B. skill/agent만 변환 | C. skill/agent + 최소 Codex hook |
|---|---|---|---|
| secret guardrail | `.claude/settings.json` hook 변환물이 생기지만 의미 재검토 필요 | `.env` hook 없음 | `.env`만 custom PreToolUse hook으로 차단 |
| live provider guardrail | skill 문서에 남음 | skill 문서에 남음 | skill 문서와 read-only reviewer로 분리 |
| Claude metadata 처리 | `model: sonnet`, `tools` review 필요 | 수동 정리 가능 | 수동 정리 가능 |
| workflow 안정성 | hook/config가 한번에 늘어남 | 낮은 위험 | 낮은 위험 + secret 보호 |
| 검증 비용 | 높음 | 낮음 | 중간 |

## 결정 (Decision)

C를 채택한다. `new-backend`는 Codex skill로 옮기고, `backend-contract-reviewer`는 `sandbox_mode = "read-only"` Codex agent로 재작성한다. `.env` 직접 편집 차단은 project `.codex/hooks.json`의 최소 PreToolUse hook으로 채택한다. Ruff 자동수정 hook은 Codex/Claude lifecycle 차이 때문에 자동 이전하지 않는다.

## 결과 및 재평가 조건 (Consequences)

- 이 선택으로 감수하는 것: ruff 자동수정은 hook이 아니라 명시 검증 명령으로 유지한다.
- 재평가 트리거: Codex hook payload/matcher가 바뀌거나, provider secret 관리 방식을 `.env`에서 다른 secret manager로 바꿀 때.
