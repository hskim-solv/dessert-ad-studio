# 0015. Agent Team Operating Model

- 날짜: 2026-06-17
- 상태: 채택됨

## 배경 (Context)

프로젝트 목표는 Agentic RAG system 자체뿐 아니라, 장기 작업을 안전하게
진행할 수 있는 AI agent 팀 운영 능력을 보여주는 것이다. Better Stack의
multi-agent C compiler 사례는 중앙 저장소, 격리 workspace, task lock, fast test
harness, external memory, 역할 분리가 agent team을 운영 가능하게 만드는 핵심
패턴임을 보여준다.

이 저장소에는 이미 CI, evidence map, ADR, redaction policy가 있으므로 완전한
16-agent swarm보다 작은 규모의 운영 모델을 먼저 적용한다. paid API, cloud,
destructive cleanup, broad retention 변경은 기존 tripwire를 유지한다.

## 선택 기준 (Criteria)

- 충돌 방지: 여러 agent가 같은 파일을 동시에 수정하지 않도록 해야 한다.
- 검증 속도: 전체 regression 전에 lane별 fast gate를 실행할 수 있어야 한다.
- 포트폴리오 신호: agent system을 만드는 것뿐 아니라 agent team을 운영하는 역량이
  문서와 재현 명령으로 드러나야 한다.
- 비용 통제: subagent/API 비용과 실행 시간을 불필요하게 키우지 않아야 한다.
- 기존 규칙 호환: main writer 1명, read-only subagent 2명 기본값과 충돌하지 않아야
  한다.

## 후보 비교 (Comparison)

| 기준 | A. 단일 main writer 유지 | B. read-only scouts + main writer | C. 제한적 multi-writer worktree | D. 완전 RALPH/Docker swarm |
|---|---|---|---|---|
| 충돌 방지 | 가장 높음 | 높음. subagent는 읽기 전용 | 중간. task lock과 disjoint write scope 필요 | 낮음-중간. 강한 lock/merge 자동화 필요 |
| 검증 속도 | 낮음. 모든 판단이 순차 | 중간. 조사/검증 후보를 병렬화 | 높음. 구현도 병렬화 가능 | 높음. 지속 worker 가능 |
| 포트폴리오 신호 | 약함 | 중간. 운영 규칙이 보임 | 높음. 사람 팀과 유사한 구조 | 높음이나 과도한 장치가 본질을 흐릴 수 있음 |
| 비용 통제 | 높음 | 높음 | 중간 | 낮음 |
| 기존 규칙 호환 | 높음 | 높음 | 조건부. 사용자 승인 또는 명시적 lane 필요 | 낮음 |
| 도입 비용 | 없음 | 낮음 | 중간 | 높음 |

## 결정 (Decision)

기본 운영 모델은 **B. read-only scouts + main writer**로 채택한다. 큰 작업에서만
명시적으로 **C. 제한적 multi-writer worktree**를 허용한다.

적용 규칙:

- main agent가 단일 writer와 통합자 역할을 맡는다.
- subagent는 기본적으로 read-only scout/reviewer/test-planner 역할만 맡는다.
- 구현 병렬화가 필요하면 task마다 disjoint write scope를 먼저 선언하고, task lock을
  만든 뒤 worktree 단위로 실행한다.
- lane별 fast gate를 먼저 실행하고, 통합 전에는 전체 regression과 CI를 확인한다.
- task 상태와 운영 규칙은 `docs/agent-workflow/`에 남긴다.

## 결과 및 재평가 조건 (Consequences)

- 이 선택으로 감수하는 것:
  - 작은 작업은 구현 병렬화보다 main writer가 빠를 수 있다.
  - multi-writer mode는 문서/테스트/write ownership 준비가 있을 때만 쓴다.
  - 완전 자동 RALPH loop, Docker worker swarm, background daemon은 아직 도입하지
    않는다.
- 재평가 트리거:
  - 한 milestone이 3개 이상의 독립 구현 lane으로 분해된다.
  - 전체 pytest 시간이 반복적으로 agent cycle을 막는다.
  - 같은 파일 충돌이 반복된다.
  - long-running autonomous worker가 필요해지고 storage/retention/scope 정책이 먼저
    정해진다.
