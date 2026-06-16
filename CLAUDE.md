# Dessert Ad Studio

카페/디저트 광고 프로토타입: Streamlit UI → FastAPI → 백엔드 어댑터(카피 3종 + SNS 이미지 1장) + Triton `template_scorer`.

## Commands

```bash
pytest -q                                  # 테스트 (venv: .venv)
ruff check .                               # 린트 (편집 시 hook이 자동 fix+format)
uvicorn api.main:app --reload --port 8000  # API
streamlit run app/streamlit_app.py         # UI
docker compose up triton -d && python scripts/triton_smoke.py   # Triton 스모크
python scripts/openai_smoke.py             # OpenAI 스모크 (OPENAI_API_KEY 필요)
```

## Architecture

- `src/dessert_ad_studio/` — 패키지 본체 (pytest `pythonpath=src`)
  - `backends/base.py` — `CopyBackend`/`ImageBackend` Protocol, `CopyResult`/`ImageResult`, `AdBackendError`
  - `backends/` — `mock`, `openai_copy`, `openai_image`, `flux2` 어댑터
- `api/main.py` — `_copy_backend_for`/`_image_backend_for` 팩토리가 `COPY_BACKEND`/`IMAGE_BACKEND` 환경변수로 어댑터 선택
- `app/streamlit_app.py` — Streamlit 프런트엔드

## Backend contract (필수)

- 백엔드 인스턴스는 캐시되어 동시 요청 간 **공유**됨 → per-request 상태를 인스턴스 속성에 두지 말 것. 토큰 usage는 `CopyResult`/`ImageResult` 반환값으로 전달.
- 사용자 노출 실패는 `AdBackendError(한국어 detail, status_code)`로 raise.
- 결과 dataclass는 `frozen=True`.
- 무거운 의존성(torch/diffusers)은 메서드 내부에서 lazy import (`flux2.py` 패턴).
- reference 이미지를 무시하는 백엔드는 `supports_reference_image = False`로 선언하고 업로드를 거부.
- 새 백엔드 추가는 4종 세트: 어댑터 + 팩토리 등록 + `tests/test_*_backend.py` + `.env.example` 갱신 → `/new-backend` 스킬 사용.

## Conventions

- 광고 카피는 항상 한국어 3종 옵션.
- 시크릿은 `.env`(커밋 금지, hook이 편집 차단), 문서화는 `.env.example`.
- 산출물은 `outputs/`, `logs/`(gitignored). 생성 이력은 `GENERATION_LOG_PATH` JSONL.
- 백엔드/`api/main.py` 변경 후에는 `backend-contract-reviewer` 에이전트로 계약 준수 검토.
- 도구/기술 채택 결정은 비교표와 함께 `docs/adr/`에 기록 (`docs/adr/template.md` 참조).

## Agentic hardening

- handoff_contract: `new-backend` skill과 `backend-contract-reviewer` handoff는 destination, input payload, input filter, return contract를 명시한 경우에만 실행한다.
- guardrail tripwires: destructive 파일 삭제, live API/OpenAI smoke, external-production 배포 영향, credential 접근, scope broadening은 실행 직전 범위와 rollback 조건을 확인한다.
- sensitive_trace_policy: raw model/tool inputs, reference image, prompt, 생성 결과, API 응답은 persistent capture 대상에서 제외하고 redaction된 요약과 test evidence만 남긴다.
- skill_quality_contract: repo-local skill은 trigger-focused frontmatter, progressive disclosure, lack of surprise, negative/non-trigger 조건을 포함한다.
- memory daemons, telemetry, cloud/API-key 서비스, vector DB, background worker는 storage location, retention, user/project/entity scope가 명시되기 전에는 추가하지 않는다.
