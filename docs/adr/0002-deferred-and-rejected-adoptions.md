# 0002. 보류·미채택 결정 및 유지보수 채택

- 날짜: 2026-06-11
- 상태: 채택됨
- 관련: [0001](0001-claude-code-automation-tooling.md)

## 배경 (Context)

"가이드가 없었다면 무엇을 다르게 채택했을까"라는 카운터팩추얼 검토 결과, 가이드 의존적 채택은 Triton(평가 가치)과 FLUX.2 자체 서빙 헤지($30 크레딧 + 제공 GPU) 두 건으로 확인됐다. 과제가 아직 진행 중이므로(가이드 유효, PR #1 머지 완료) 현시점 결정을 기록한다. 미채택·보류 기록은 채택 기록과 동일하게 재평가 조건을 가진다.

## 결정 1: Triton 유지 (onnxruntime 전환 보류)

선택 기준: 과제 평가 가치, 전환 작업 비용, 운영 단순성.

| 기준 | Triton 유지 ✅ | onnxruntime 인프로세스 전환 |
|---|---|---|
| 과제 평가 가치 ("모델 배포하기" 증빙) | 유지 | 상실 |
| 운영 단순성 | 컨테이너 1개 + 네트워크 홉 부담 | 단순 (의존성 1개) |
| 전환 비용 | 0 | triton.py·docker-compose·테스트 재작업 |
| 현재 문제 유발 여부 | 없음 (`REQUIRE_TRITON=0` 기본으로 로컬 우회 가능) | - |

**선택 이유**: 단일 소형 ONNX 스코어러에 Triton은 엔지니어링 관점에서 과투자지만, 과제 정체성("모델 배포하기")에서 평가 가치가 전환 이득을 상회한다. **재평가 트리거**: 과제 종료. 종료 후에는 onnxruntime 인프로세스로 간소화가 기본 권고.

## 결정 2: LLM 관측성(observability) 도구 미채택 (JSONL 로거 유지)

선택 기준: 과제 스케일 적합성, 도입 비용, 비용 추적 능력, self-host 가능성.

| 기준 | 현행 JSONL ✅ | Langfuse | LangSmith | Helicone |
|---|---|---|---|---|
| 과제 스케일(단일 팀, $30 한도)에 충분 | O | 과투자 | 과투자 | 과투자 |
| 도입 비용 | 0 (이미 구현) | self-host 구축 필요 | SaaS 계정·키 관리 | 프록시 경유 변경 |
| 비용/토큰 추적 | O (usage 기록 중) | O | O | O |
| 오픈소스/self-host | - | O/O | X/X | 부분/X |
| 프레임워크 독립 (LangChain 미사용) | O | 우수 | O (단, LC 중심) | O |

**선택 이유**: 가이드 요구(로깅·모니터링)와 $30 한도 추적은 JSONL + usage 반환 계약으로 이미 충족된다. **재평가 트리거**: 실서비스 전환 또는 다중 사용자 트래픽 발생. 그 시점 후보 1순위는 프로파일(LangChain 미사용, self-host 선호, 비용 추적 필수)상 Langfuse.

## 결정 3: httpx2를 dev 의존성으로 채택 (강제된 마이그레이션)

업스트림 강제 사항이라 풀 비교 생략 (전역 규칙의 trivial 선택 조항). starlette 1.2.1의 `testclient`가 `httpx2`를 직접 import하며 httpx 사용 시 deprecation 경고를 낸다.

- **출처 검증**: PyPI 메타데이터 — 원작자 Tom Christie 작성, Pydantic Services Inc. 유지보수, 저장소 `pydantic/httpx2`. typosquat 아님을 확인 후 선언.
- **범위**: dev extras만. 런타임 `httpx`는 유지 — `app/streamlit_app.py`가 직접 사용하고 OpenAI SDK의 전이 의존성이기도 함.
- **재평가 트리거**: OpenAI SDK 또는 starlette 런타임이 httpx2를 요구하는 시점에 런타임 마이그레이션.

## 결정 4: ruff format 일괄 적용 + CI 강제 (ADR-0001 트리거 이행)

ADR-0001 결정 3의 재평가 조건("일회성 `ruff format .` 커밋 후 CI에 format check 추가")이 PR #1 머지로 충족되어 이행했다. 10개 파일 일괄 포맷 후 66개 테스트 통과 확인, CI에 `ruff format --check .` 추가.

## 리스크 기록: flux2의 reference 이미지(i2i) 미지원

- 현황: OpenAI 이미지 백엔드는 `images.edit`로 reference를 지원하지만 flux2는 t2i 전용(`supports_reference_image = False`).
- 리스크: $30 한도 소진으로 flux2 fallback 전환 시, 가이드 기능 예시 2~4(레퍼런스/제품 보존 생성)를 동반 상실.
- **대응 트리거**: OpenAI 사용량이 한도의 80% 도달 시 flux2 i2i 파이프라인(IP-Adapter/ControlNet 계열) 작업 착수.

## 결과 및 재평가 조건 (Consequences)

- 감수하는 것: Triton 운영 복잡도(과제 기간 한정), 관측성 공백(과제 스케일에선 무시 가능).
- 재평가 트리거 요약: 과제 종료(결정 1) / 실서비스 전환(결정 2) / 업스트림 런타임 요구(결정 3) / 사용량 80%(리스크).
