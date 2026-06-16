# 0009. OpenAI Vision Product Analysis

- 날짜: 2026-06-16
- 상태: 채택됨

## 배경 (Context)

M4 목표는 mock product analysis를 실제 vision-capable analyzer로 교체할 수
있는 production path를 추가하는 것이다. 이 단계는 제품 사진 보존형 광고 생성
서비스의 핵심 포트폴리오 신호인 `VLM product analysis -> copy/image workflow`
연결을 보여줘야 한다.

현재 제약:

- raw reference image, raw prompt, raw model response는 persistent trace/history에
  저장하지 않는다.
- live API smoke는 `OPENAI_API_KEY`와 비용이 필요하므로 명시 승인 전에는 실행하지
  않는다.
- 기존 OpenAI copy/image backend와 같은 `AdBackendError` contract를 따라야 한다.
- backend 인스턴스는 캐시/공유될 수 있으므로 per-request mutable state를 두지
  않는다.

## 선택 기준 (Criteria)

- Portfolio signal: Korean multimodal AI/backend 공고에서 VLM, OpenAI API,
  structured output, 운영 가능한 API 통합 신호가 강해야 한다.
- Integration speed: 현재 OpenAI copy/image backend와 환경변수/에러 처리 패턴을
  재사용할 수 있어야 한다.
- Structured reliability: `ProductAnalysis`에 가까운 schema adherence가 필요하다.
- Data policy: request-level image/text를 durable storage에 남기지 않고, provider
  기본 저장 동작도 가능한 한 끈다.
- Cost and latency: demo path에서 p95 30초 목표 안에 들어갈 가능성이 높아야 한다.
- Reversibility: Gemini, local Florence류 모델로 바꾸더라도 `ProductAnalyzer`
  protocol은 유지되어야 한다.

## 후보 비교 (Comparison)

| 기준 | OpenAI Responses Vision | Gemini Vision | Local Florence-2/BLIP 계열 |
|---|---|---|---|
| Portfolio signal | OpenAI multimodal API + structured output + production backend 통합 신호가 강함. | Google multimodal API 신호가 강하지만 현재 repo의 OpenAI copy/image lane과 분리됨. | Local VLM 운영 신호는 좋지만 품질/한국어 schema 안정성 검증 부담이 큼. |
| Integration speed | 기존 `OPENAI_API_KEY`, OpenAI SDK, `AdBackendError` 패턴을 재사용. | 새 SDK/env/error mapping 필요. | 모델 다운로드, GPU/CPU 성능, serving path가 추가됨. |
| Structured reliability | Responses API `responses.parse(..., text_format=...)`로 Pydantic 구조화 출력 가능. | JSON schema/structured output 검증 가능하지만 별도 패턴 도입 필요. | 후처리/파싱/검증이 더 필요함. |
| Data policy | `store=False`로 provider 저장을 끄고, local durable history에는 요약만 남김. | 유사 정책 설계 필요. | 외부 전송은 줄지만 모델/이미지 artifact storage 정책이 필요함. |
| Cost and latency | 유료 API지만 local infra 부담 없이 demo latency 목표에 맞추기 쉬움. | 유료 API이며 별도 quota/latency 검증 필요. | API 비용은 줄 수 있으나 로컬 추론 latency와 용량 부담이 큼. |
| Reversibility | `ProductAnalyzer` adapter 하나로 격리 가능. | 같은 protocol adapter로 전환 가능. | 같은 protocol adapter로 전환 가능하지만 serving layer가 커짐. |

## 결정 (Decision)

Adopt OpenAI Responses Vision as the first real product-analysis backend.

결정 요인은 현재 서비스의 완성도와 포트폴리오 신호를 가장 빠르게 올리는 조합이다.
OpenAI는 이미 copy/image backend가 있어 운영 surface가 작고, Responses API는
vision 입력과 structured outputs를 함께 제공한다. 구현은 `PRODUCT_ANALYSIS_BACKEND=openai`
로 opt-in하고 default는 `mock`으로 유지한다.

Implementation defaults:

- `OpenAIProductAnalyzer`는 `client.responses.parse(..., text_format=...)`를 사용한다.
- reference image는 request 안에서만 base64 data URL로 전달하고 저장하지 않는다.
- `store=False`를 명시해 provider-side response storage를 끈다.
- `PRODUCT_ANALYSIS_MODEL_ID`를 별도 환경변수로 둔다.
- live smoke는 별도 승인 후 실행한다.

## Storage, Retention, And Scope

- Local durable storage: 없음. Analyzer는 raw image, raw prompt, raw model response를
  파일/DB/log에 저장하지 않는다.
- Provider request: OpenAI API 호출 시 product request text와 optional reference
  image data URL이 전송된다.
- Provider storage: Responses API 요청에 `store=False`를 사용한다.
- Project scope: 이 adapter는 Dessert Ad Studio 전용이며 global daemon, memory,
  cross-project telemetry가 아니다.

## 결과 및 재평가 조건 (Consequences)

- 이 선택으로 감수하는 것:
  - OpenAI API key와 유료 호출이 필요하다.
  - image input 비용/latency는 실제 smoke/eval 전까지 추정치다.
  - provider에 제품 요청 텍스트와 reference image가 전송된다.
- 재평가 트리거:
  - OpenAI path p95가 30초를 넘거나 demo latency가 불안정하다.
  - structured output refusal/parse failure가 반복된다.
  - 고객 이미지 외부 전송을 허용하지 않는 요구가 생긴다.
  - Gemini 또는 local VLM이 같은 schema 품질을 더 낮은 비용/latency로 입증한다.

## Source Notes

- OpenAI docs recommend the Responses API for new direct model requests and
  describe it as supporting text and image inputs.
- OpenAI vision docs list the Responses API as an image-analysis path.
- OpenAI structured-output docs show Python `client.responses.parse` with
  `text_format=<PydanticModel>` and `response.output_parsed`.
- OpenAI response API reference documents `input_image` and base64 data URL
  image inputs.
