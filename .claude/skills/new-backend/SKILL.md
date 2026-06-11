---
name: new-backend
description: Use when adding a new copy or image generation backend adapter to dessert-ad-studio (e.g. gemini, anthropic, replicate), or when wiring a new COPY_BACKEND/IMAGE_BACKEND option end to end.
---

# New Backend Adapter

`$ARGUMENTS` 백엔드를 추가한다. 기존 어댑터 4개(`mock`, `openai_copy`, `openai_image`, `flux2`)와 같은 패턴을 따르며, 아래 4종 세트가 모두 갖춰져야 완료다.

## 1. 어댑터 구현 — `src/dessert_ad_studio/backends/<name>.py`

- `backends/base.py`의 `CopyBackend` 또는 `ImageBackend` Protocol을 구조적으로 만족시킨다 (상속 아님, 메서드 시그니처 일치).
- 가장 가까운 기존 어댑터를 먼저 읽고 따라 한다: 카피 백엔드는 `openai_copy.py`, 이미지 백엔드는 `openai_image.py` 또는 `flux2.py`.
- 계약 (위반 시 과거 버그 재발):
  - 인스턴스는 캐시되어 동시 요청 간 공유됨 → per-request 상태(usage 등)는 인스턴스 속성 금지, `CopyResult`/`ImageResult` 반환값으로 전달.
  - 사용자 노출 실패는 `AdBackendError(한국어 detail, status_code)`.
  - API 키는 생성 시점에 빈/공백 검사 (fail-fast).
  - reference 이미지를 사용하지 않으면 `supports_reference_image = False` 선언.
  - 무거운 의존성은 메서드 내부 lazy import (`flux2.py:_load_pipeline` 패턴).
  - 파일명은 `backends/naming.py`의 `safe_filename_stem` 사용.

## 2. 팩토리 등록 — `api/main.py`

`_copy_backend_for` 또는 `_image_backend_for`에 이름 분기를 추가한다. 모델 ID 등은 `os.getenv`로 읽고 기본값을 둔다.

## 3. 테스트 — `tests/test_<name>_backend.py`

`tests/test_openai_copy_backend.py`(카피) 또는 `tests/test_openai_image_backend.py`(이미지)의 구조를 따른다. 외부 API는 클라이언트를 fake/monkeypatch로 대체. 최소 커버: 정상 경로의 결과+usage 반환, API 키 누락 시 fail-fast, 백엔드 에러 → `AdBackendError` 변환.

## 4. 환경변수 문서화 — `.env.example`

새 변수(`<NAME>_MODEL_ID` 등)를 기본값과 함께 추가한다. `.env`는 직접 수정하지 않는다 (hook이 차단).

## 완료 검증

```bash
pytest -q && ruff check .
```

전부 통과 후 `backend-contract-reviewer` 에이전트로 계약 준수를 검토한다.
