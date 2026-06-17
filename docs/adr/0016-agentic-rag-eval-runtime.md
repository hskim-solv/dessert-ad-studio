# 0016. Agentic RAG Eval Runtime

- 날짜: 2026-06-17
- 상태: 채택됨

## 배경 (Context)

M9 first gate는 `scripts/agentic_rag_eval_guardrail.py`로 13개 golden case를
오프라인에서 실행하고 Ragas/promptfoo-compatible summary를 만든다. 이 gate는
빠르고 paid API를 호출하지 않지만, 포트폴리오 최종 목표의 "Ragas + promptfoo
golden eval" 요구를 완전히 증명하지는 않는다.

실제 패키지 실행으로 승격할 때도 기본 CI는 무료, 빠른, 결정적 경로를 유지해야
한다. `ragas`의 faithfulness, answer relevancy, context precision/recall 계열
평가는 evaluator LLM/embedding이 필요한 구성이 많으므로 paid API 사용과 비용
정책을 분리해야 한다. `promptfoo`는 custom script/exec provider로 로컬 회귀
테스트를 실행할 수 있어 기본 CI gate에 먼저 올리기 적합하다.

## 선택 기준 (Criteria)

| 기준 | 이유 |
|---|---|
| 기본 CI 결정성 | PR마다 외부 모델 품질/속도/비용에 흔들리면 regression gate가 약해진다. |
| 실제 도구 실행 증거 | compatibility JSON만으로는 Ragas/promptfoo 요구를 충분히 어필하기 어렵다. |
| paid API 격리 | 평가 LLM 비용과 rate limit은 사용자 승인 없이 기본 CI에 넣지 않는다. |
| golden dataset 재사용 | 기존 13-case guardrail/retrieval evidence를 새 도구가 그대로 소비해야 한다. |
| redaction 유지 | raw prompt, reference image, model response, secret-like text를 artifact에 남기지 않는다. |
| CI runtime budget | 기본 eval gate는 60초 안팎을 목표로 하고, live semantic eval은 수동 job으로 분리한다. |

## 후보 비교 (Comparison)

| 기준 | 후보 A: 오프라인 promptfoo 회귀 게이트 + 선택적 Ragas live 게이트 | 후보 B: Ragas + promptfoo 모두 기본 CI에서 실행 | 후보 C: 현재 compatibility gate 유지 |
|---|---|---|---|
| 기본 CI 결정성 | 높음. promptfoo는 local exec provider로 기존 deterministic summary를 검증한다. | 낮음. Ragas evaluator LLM/embedding 호출이 외부 상태에 의존한다. | 높음. 새 dependency가 없다. |
| 실제 도구 실행 증거 | 중간에서 높음. promptfoo는 기본 CI 후보이고 Ragas는 승인형 live gate로 남긴다. | 높음. 두 패키지 모두 매번 실행된다. | 낮음. 실제 패키지 실행이 없다. |
| paid API 격리 | 높음. Ragas live gate는 `OPENAI_API_KEY`와 명시적 실행이 있을 때만 돈다. | 낮음. 기본 CI가 paid API/rate limit에 노출된다. | 높음. paid API 없음. |
| golden dataset 재사용 | 높음. 기존 summary script를 provider로 감싼다. | 중간. Ragas dataset 변환 계층을 별도로 관리해야 한다. | 높음. 현재 구조 그대로다. |
| redaction 유지 | 높음. 기존 redaction checks를 promptfoo assertion으로 다시 검증한다. | 중간. Ragas trace/result payload를 별도 검토해야 한다. | 높음. 현재 checks 유지. |
| CI runtime budget | 높음. promptfoo wrapper만 실행하면 bounded runtime이다. | 낮음. evaluator 모델 호출 수만큼 늘어난다. | 높음. 현재 1초대 script gate다. |

## 결정 (Decision)

오프라인 promptfoo 회귀 게이트 + 선택적 Ragas live 게이트를 채택한다.

- 기본 CI 승격 대상:
  - `evals/promptfoo/agentic-rag.yaml`
  - `scripts/promptfoo_agentic_rag_provider.py`
  - `scripts/agentic_rag_promptfoo_package_smoke.py`
  - 기존 `scripts/agentic_rag_eval_guardrail.py` summary를 promptfoo provider output으로 재사용
- 선택적 live gate:
  - `ragas>=0.4,<0.5`, `datasets`, `langchain-openai`를 `eval` optional dependency로 둔다.
  - evaluator LLM이 필요한 Ragas gate는 paid API 사용 승인 후 수동으로 실행한다.
- 현재 CI의 `Agentic RAG eval guardrail gate`는 유지하고,
  `Agentic RAG promptfoo package gate`를 추가한다. Node dependency는
  `package-lock.json`과 `npm ci --no-audit --no-fund`로 고정하고, promptfoo
  실행은 `--no-cache --no-progress-bar --no-table`과 telemetry disable 환경으로
  bounded 실행한다.

## 결과 및 재평가 조건 (Consequences)

- 이 선택으로 감수하는 것:
  - Ragas live gate가 기본 CI의 항상-실행 evidence가 되지는 않는다.
  - promptfoo package gate는 기본 CI에 들어갔지만, Ragas semantic metric은 비용
    승인과 evaluator 모델 안정성 확인이 필요하다.
  - compatibility summary와 promptfoo assertion 사이의 중복을 유지한다.
- 재평가 트리거:
  - 기본 CI에서 promptfoo 실행이 60초를 초과하거나 flake가 발생한다.
  - Ragas live gate 비용이 회귀당 0.25 USD를 넘는다.
  - evaluator LLM 변경으로 metric drift가 커져 release-to-release 비교가 어려워진다.
  - golden dataset이 50 cases 이상으로 커져 local exec provider 방식이 느려진다.
  - promptfoo가 Python provider/exec provider 설정을 breaking-change로 바꾼다.
