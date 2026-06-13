# Controlled Workflow and A2A Spike Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the current `/generate` path into a typed, testable workflow and expose one A2A-compatible ad-generation capability as a narrow interoperability spike.

**Architecture:** Keep FastAPI, Streamlit, backend adapters, Triton/ONNX, and PIL overlay unchanged. Add a focused `workflow.py` that owns generation orchestration, then add an `a2a.py` facade that publishes an Agent Card and accepts a synchronous A2A-style `SendMessage` request for one `generate_ad_banner` skill.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, pytest, existing backend adapters, existing `httpx` dependency for smoke testing. No Redis, no LangGraph dependency, and no official A2A SDK in this first spike.

---

## Scope

This plan implements only:

- typed workflow extraction around the existing generation behavior
- step trace metadata for internal evidence
- A2A Agent Card discovery at `/.well-known/agent-card.json`
- A2A HTTP binding smoke path at `POST /message:send`
- task retrieval at `GET /tasks/{id}`
- docs and smoke test for the A2A spike

This plan does not implement:

- Redis/RQ/Celery job queue
- LangGraph dependency
- RAG
- OpenTelemetry/Langfuse/Phoenix
- FastMCP
- streaming A2A
- push notifications
- authenticated extended Agent Card
- OpenInference/OpenTelemetry GenAI instrumentation
- LiteLLM Gateway
- Qwen-Image/Qwen-Image-Edit

Those three candidates are recorded in the A-to-Z spec as follow-up candidates. They belong in later plans:

- Observability plan: OpenTelemetry GenAI/MCP semantic conventions plus OpenInference, exported to Langfuse or Phoenix.
- Provider-routing plan: LiteLLM Gateway only after multiple active text/eval providers need fallback, budgets, or cost attribution.
- Image experiment plan: Qwen-Image/Qwen-Image-Edit comparison while keeping deterministic Korean PIL overlay as the default.

## Source Notes

- A2A positions itself as agent-to-agent communication, while MCP remains agent-to-tool communication.
- A2A Agent Cards are commonly exposed at `/.well-known/agent-card.json`.
- A2A HTTP examples use `POST /message:send` and `Content-Type: application/a2a+json`.
- A2A basic task responses contain a `task` with `id`, `contextId`, `status.state`, and optional `artifacts`.

## File Structure

- Create `src/dessert_ad_studio/workflow.py`
  - Owns the generation orchestration currently embedded in `api/main.py`.
  - Defines dependency and trace dataclasses.
  - Returns `GenerationWorkflowOutput` with `response` and `trace`.

- Create `src/dessert_ad_studio/a2a.py`
  - Defines small Pydantic models for the A2A subset used by this project.
  - Builds the public Agent Card.
  - Converts A2A structured input into `GenerationRequest`.
  - Converts `GenerationResponse` into a completed A2A task artifact.
  - Keeps an in-memory task store for the synchronous spike.

- Modify `api/main.py`
  - Keep backend factory functions and health/metrics endpoints.
  - Replace inline `/generate` orchestration with `run_generation_workflow`.
  - Add Agent Card, `POST /message:send`, and `GET /tasks/{task_id}` endpoints.

- Create `tests/test_workflow.py`
  - Unit-tests the workflow without HTTP.

- Modify `tests/test_api.py`
  - Add A2A Agent Card, send-message, task retrieval, and invalid-input tests.

- Create `scripts/a2a_smoke.py`
  - Runs a local HTTP smoke against the A2A endpoints.

- Modify `README.md`
  - Document the A2A spike and when to use it versus normal REST API.

---

### Task 1: Extract Generation Workflow

**Files:**
- Create: `src/dessert_ad_studio/workflow.py`
- Test: `tests/test_workflow.py`

- [ ] **Step 1: Write failing workflow test**

Create `tests/test_workflow.py`:

```python
from pathlib import Path

from dessert_ad_studio.backends.mock import MockAdBackend
from dessert_ad_studio.product_analysis import MockProductAnalyzer
from dessert_ad_studio.schemas import GenerationRequest
from dessert_ad_studio.triton import LocalTemplateScorer
from dessert_ad_studio.workflow import GenerationWorkflowDependencies, run_generation_workflow


def request_payload() -> GenerationRequest:
    return GenerationRequest(
        campaign_purpose="new_menu",
        product_name="말차 푸딩",
        tone="clean",
        template_hint="minimal_premium",
        price_text="5,500원",
        user_constraints="깔끔한 프리미엄 느낌",
    )


def test_workflow_returns_generation_response_and_trace(tmp_path: Path) -> None:
    backend = MockAdBackend(output_dir=str(tmp_path))
    deps = GenerationWorkflowDependencies(
        template_scorer=LocalTemplateScorer(),
        copy_backend=backend,
        image_backend=backend,
        product_analyzer=MockProductAnalyzer(),
        log_path=tmp_path / "generations.jsonl",
    )

    output = run_generation_workflow(request_payload(), deps)

    assert output.response.copy_backend == "mock"
    assert output.response.image_backend == "mock"
    assert output.response.product_analysis.analyzer_backend == "mock"
    assert output.response.image_path.endswith(".png")
    assert [entry.step for entry in output.trace] == [
        "rank_templates",
        "decode_reference",
        "analyze_product",
        "build_image_prompt",
        "generate_copy",
        "generate_image",
        "write_log",
    ]
    assert output.trace[-1].metadata["log_path"].endswith("generations.jsonl")
```

- [ ] **Step 2: Run failing workflow test**

Run:

```bash
pytest tests/test_workflow.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'dessert_ad_studio.workflow'
```

- [ ] **Step 3: Add workflow implementation**

Create `src/dessert_ad_studio/workflow.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any

from dessert_ad_studio.backends.base import CopyBackend, ImageBackend
from dessert_ad_studio.generation_logger import GenerationLogger
from dessert_ad_studio.prompts import build_image_prompt
from dessert_ad_studio.product_analysis import ProductAnalyzer
from dessert_ad_studio.reference_image import decode_reference_image
from dessert_ad_studio.schemas import GenerationRequest, GenerationResponse, TemplateRanking


@dataclass(frozen=True)
class WorkflowTraceEntry:
    step: str
    elapsed_ms: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GenerationWorkflowDependencies:
    template_scorer: Any
    copy_backend: CopyBackend
    image_backend: ImageBackend
    product_analyzer: ProductAnalyzer
    log_path: Path


@dataclass(frozen=True)
class GenerationWorkflowOutput:
    response: GenerationResponse
    trace: list[WorkflowTraceEntry]


def _trace_step(
    trace: list[WorkflowTraceEntry],
    step: str,
    started: float,
    metadata: dict[str, Any] | None = None,
) -> None:
    trace.append(
        WorkflowTraceEntry(
            step=step,
            elapsed_ms=round((perf_counter() - started) * 1000, 3),
            metadata=metadata or {},
        )
    )


def run_generation_workflow(
    request: GenerationRequest,
    dependencies: GenerationWorkflowDependencies,
) -> GenerationWorkflowOutput:
    workflow_started = perf_counter()
    trace: list[WorkflowTraceEntry] = []

    step_started = perf_counter()
    ranking: TemplateRanking = dependencies.template_scorer.rank(request)
    _trace_step(
        trace,
        "rank_templates",
        step_started,
        {
            "template": ranking.template_name,
            "scorer": ranking.scorer,
            "latency_ms": ranking.latency_ms,
        },
    )

    step_started = perf_counter()
    reference_image = decode_reference_image(request.reference_image_b64)
    _trace_step(
        trace,
        "decode_reference",
        step_started,
        {
            "has_reference": reference_image is not None,
            "reference_image_name": request.reference_image_name,
        },
    )

    step_started = perf_counter()
    product_analysis = dependencies.product_analyzer.analyze(
        request,
        reference_image=reference_image,
    )
    _trace_step(
        trace,
        "analyze_product",
        step_started,
        {"analyzer_backend": dependencies.product_analyzer.name},
    )

    step_started = perf_counter()
    image_prompt = build_image_prompt(
        request,
        ranked_template=ranking.template_name,
        has_reference=reference_image is not None,
    )
    _trace_step(
        trace,
        "build_image_prompt",
        step_started,
        {"prompt_preview": image_prompt[:120]},
    )

    step_started = perf_counter()
    copy_result = dependencies.copy_backend.generate_copy(request)
    _trace_step(
        trace,
        "generate_copy",
        step_started,
        {"copy_backend": dependencies.copy_backend.name},
    )

    step_started = perf_counter()
    image_result = dependencies.image_backend.generate_image(
        request,
        image_prompt=image_prompt,
        reference_image=reference_image,
    )
    _trace_step(
        trace,
        "generate_image",
        step_started,
        {
            "image_backend": dependencies.image_backend.name,
            "image_path": image_result.image_path,
        },
    )

    response = GenerationResponse(
        copy_options=copy_result.copy_options,
        selected_template=ranking,
        image_path=image_result.image_path,
        image_backend=dependencies.image_backend.name,
        copy_backend=dependencies.copy_backend.name,
        used_reference=reference_image is not None,
        prompt_summary=image_prompt,
        elapsed_ms=round((perf_counter() - workflow_started) * 1000, 2),
        product_analysis=product_analysis,
    )

    step_started = perf_counter()
    logger = GenerationLogger(dependencies.log_path)
    logger.write(
        {
            "campaign_purpose": request.campaign_purpose,
            "template": ranking.template_name,
            "template_scorer": ranking.scorer,
            "triton_latency_ms": ranking.latency_ms,
            "copy_backend": dependencies.copy_backend.name,
            "copy_model_id": getattr(dependencies.copy_backend, "model_id", None),
            "image_backend": dependencies.image_backend.name,
            "image_model_id": getattr(dependencies.image_backend, "model_id", None),
            "product_analysis_backend": dependencies.product_analyzer.name,
            "used_reference": reference_image is not None,
            "reference_image_name": request.reference_image_name,
            "workflow_trace": [
                {
                    "step": entry.step,
                    "elapsed_ms": entry.elapsed_ms,
                    "metadata": entry.metadata,
                }
                for entry in trace
            ],
        }
    )
    _trace_step(
        trace,
        "write_log",
        step_started,
        {"log_path": str(dependencies.log_path)},
    )

    return GenerationWorkflowOutput(response=response, trace=trace)
```

- [ ] **Step 4: Run workflow test**

Run:

```bash
pytest tests/test_workflow.py -q
```

Expected:

```text
1 passed
```

- [ ] **Step 5: Commit workflow extraction base**

Run:

```bash
git add src/dessert_ad_studio/workflow.py tests/test_workflow.py
git commit -m "Add typed generation workflow"
```

Expected:

```text
[main <hash>] Add typed generation workflow
```

---

### Task 2: Route FastAPI `/generate` Through Workflow

**Files:**
- Modify: `api/main.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Add regression assertion for existing `/generate` behavior**

Modify `tests/test_api.py` inside `test_generate_uses_template_ranking_and_returns_copy` by adding:

```python
    assert payload["product_analysis"]["analyzer_backend"] == "mock"
    assert payload["elapsed_ms"] >= 0
```

- [ ] **Step 2: Run the targeted API test before refactor**

Run:

```bash
pytest tests/test_api.py::test_generate_uses_template_ranking_and_returns_copy -q
```

Expected:

```text
1 passed
```

- [ ] **Step 3: Modify imports in `api/main.py`**

Add these imports:

```python
from dessert_ad_studio.workflow import (
    GenerationWorkflowDependencies,
    run_generation_workflow,
)
```

Keep existing imports for `build_image_prompt`, `GenerationLogger`, and `decode_reference_image` temporarily until the inline code is removed in the next step.

- [ ] **Step 4: Replace inline generation body with workflow call**

Replace the body of `generate` in `api/main.py` with:

```python
@app.post("/generate", response_model=GenerationResponse)
def generate(request: GenerationRequest) -> GenerationResponse:
    ranking_scorer = get_template_scorer()
    copy_backend = get_copy_backend()
    image_backend = get_image_backend()

    try:
        reference_image = decode_reference_image(request.reference_image_b64)
    except ReferenceImageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if reference_image is not None and not image_backend.supports_reference_image:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{image_backend.name} 이미지 백엔드는 아직 참고 이미지를 지원하지 않습니다. "
                "참고 이미지 없이 다시 시도하거나 IMAGE_BACKEND=openai로 전환해주세요."
            ),
        )

    product_analyzer = get_product_analyzer()
    dependencies = GenerationWorkflowDependencies(
        template_scorer=ranking_scorer,
        copy_backend=copy_backend,
        image_backend=image_backend,
        product_analyzer=product_analyzer,
        log_path=Path(os.getenv("GENERATION_LOG_PATH", "logs/generations.jsonl")),
    )

    try:
        return run_generation_workflow(request, dependencies).response
    except ReferenceImageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AdBackendError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
```

After replacing the body, remove unused imports from `api/main.py`:

```python
from dessert_ad_studio.generation_logger import GenerationLogger
from dessert_ad_studio.prompts import build_image_prompt
```

Keep:

```python
from dessert_ad_studio.reference_image import ReferenceImageError, decode_reference_image
```

The endpoint still decodes reference images before workflow execution so it can reject unsupported reference-image backends before spending copy tokens.

- [ ] **Step 5: Run API tests affected by refactor**

Run:

```bash
pytest tests/test_api.py::test_generate_uses_template_ranking_and_returns_copy \
  tests/test_api.py::test_generate_with_product_analysis \
  tests/test_api.py::test_generate_rejects_reference_image_for_flux2 \
  tests/test_api.py::test_flux2_reference_rejection_spends_no_copy_tokens \
  tests/test_api.py::test_generate_rejects_invalid_reference_encoding -q
```

Expected:

```text
5 passed
```

- [ ] **Step 6: Commit API workflow routing**

Run:

```bash
git add api/main.py tests/test_api.py
git commit -m "Route API generation through workflow"
```

Expected:

```text
[main <hash>] Route API generation through workflow
```

---

### Task 3: Add A2A Models and In-Memory Task Store

**Files:**
- Create: `src/dessert_ad_studio/a2a.py`
- Test: `tests/test_a2a.py`

- [ ] **Step 1: Write failing A2A model tests**

Create `tests/test_a2a.py`:

```python
from dessert_ad_studio.a2a import (
    A2ATaskStore,
    build_agent_card,
    extract_generation_request,
)


def generation_payload() -> dict:
    return {
        "campaign_purpose": "new_menu",
        "product_name": "말차 푸딩",
        "tone": "clean",
        "template_hint": "minimal_premium",
        "price_text": "5,500원",
        "user_constraints": "깔끔한 프리미엄 느낌",
    }


def test_agent_card_advertises_generate_skill() -> None:
    card = build_agent_card(base_url="http://testserver")

    assert card["name"] == "Dessert Ad Studio Agent"
    assert card["url"] == "http://testserver"
    assert card["skills"][0]["id"] == "generate_ad_banner"
    assert card["skills"][0]["inputModes"] == ["application/json"]
    assert card["skills"][0]["outputModes"] == ["application/json"]


def test_extract_generation_request_from_data_part() -> None:
    request = extract_generation_request(
        {
            "role": "ROLE_USER",
            "messageId": "msg-1",
            "parts": [{"data": generation_payload()}],
        }
    )

    assert request.product_name == "말차 푸딩"
    assert request.template_hint == "minimal_premium"


def test_task_store_saves_and_returns_task() -> None:
    store = A2ATaskStore()
    task = {
        "id": "task-1",
        "contextId": "context-1",
        "status": {"state": "TASK_STATE_COMPLETED"},
    }

    store.save(task)

    assert store.get("task-1") == task
    assert store.get("missing") is None
```

- [ ] **Step 2: Run failing A2A model tests**

Run:

```bash
pytest tests/test_a2a.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'dessert_ad_studio.a2a'
```

- [ ] **Step 3: Implement A2A subset module**

Create `src/dessert_ad_studio/a2a.py`:

```python
from __future__ import annotations

from threading import Lock
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from dessert_ad_studio.schemas import GenerationRequest, GenerationResponse


TASK_COMPLETED = "TASK_STATE_COMPLETED"
TASK_REJECTED = "TASK_STATE_REJECTED"


class A2AInputError(ValueError):
    pass


class A2ATaskStore:
    def __init__(self) -> None:
        self._tasks: dict[str, dict[str, Any]] = {}
        self._lock = Lock()

    def save(self, task: dict[str, Any]) -> None:
        with self._lock:
            self._tasks[task["id"]] = task

    def get(self, task_id: str) -> dict[str, Any] | None:
        with self._lock:
            return self._tasks.get(task_id)


def build_agent_card(base_url: str) -> dict[str, Any]:
    return {
        "name": "Dessert Ad Studio Agent",
        "description": (
            "Generates Korean small-business ad banner assets from structured product "
            "and campaign inputs."
        ),
        "url": base_url.rstrip("/"),
        "version": "0.1.0",
        "protocolVersion": "1.0",
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
            "extendedAgentCard": False,
        },
        "defaultInputModes": ["application/json"],
        "defaultOutputModes": ["application/json"],
        "supportedInterfaces": [
            {
                "protocolBinding": "HTTP+JSON",
                "url": base_url.rstrip("/"),
                "protocolVersion": "1.0",
            }
        ],
        "skills": [
            {
                "id": "generate_ad_banner",
                "name": "Generate Korean ad banner",
                "description": (
                    "Create copy, image prompt, generated visual path, and product analysis "
                    "for a small-business product ad."
                ),
                "tags": ["ad-generation", "korean-copy", "small-business", "image-generation"],
                "examples": [
                    "Generate an Instagram banner for a strawberry cake launch.",
                    "Generate a Smartstore thumbnail for a flower box discount.",
                ],
                "inputModes": ["application/json"],
                "outputModes": ["application/json"],
            }
        ],
    }


def extract_generation_request(message: dict[str, Any]) -> GenerationRequest:
    parts = message.get("parts")
    if not isinstance(parts, list) or not parts:
        raise A2AInputError("A2A message must include at least one part")

    for part in parts:
        if isinstance(part, dict) and isinstance(part.get("data"), dict):
            try:
                return GenerationRequest.model_validate(part["data"])
            except ValidationError as exc:
                raise A2AInputError(str(exc)) from exc

    raise A2AInputError("A2A generate_ad_banner expects an application/json data part")


def completed_generation_task(
    response: GenerationResponse,
    *,
    message_id: str | None,
    context_id: str | None = None,
) -> dict[str, Any]:
    task_id = f"task-{uuid4()}"
    resolved_context_id = context_id or f"context-{uuid4()}"
    return {
        "id": task_id,
        "contextId": resolved_context_id,
        "status": {
            "state": TASK_COMPLETED,
            "message": {
                "role": "ROLE_AGENT",
                "parts": [
                    {
                        "text": (
                            f"Generated {len(response.copy_options)} copy options and "
                            f"banner asset at {response.image_path}"
                        )
                    }
                ],
            },
        },
        "metadata": {
            "sourceMessageId": message_id,
            "skillId": "generate_ad_banner",
        },
        "artifacts": [
            {
                "artifactId": f"artifact-{uuid4()}",
                "name": "Dessert Ad Studio generation result",
                "parts": [{"data": response.model_dump(mode="json")}],
            }
        ],
    }
```

- [ ] **Step 4: Run A2A model tests**

Run:

```bash
pytest tests/test_a2a.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 5: Commit A2A models**

Run:

```bash
git add src/dessert_ad_studio/a2a.py tests/test_a2a.py
git commit -m "Add A2A facade models"
```

Expected:

```text
[main <hash>] Add A2A facade models
```

---

### Task 4: Add A2A FastAPI Endpoints

**Files:**
- Modify: `api/main.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: Add failing Agent Card endpoint test**

Append to `tests/test_api.py`:

```python
def test_a2a_agent_card() -> None:
    response = client.get("/.well-known/agent-card.json")

    assert response.status_code == 200
    card = response.json()
    assert card["name"] == "Dessert Ad Studio Agent"
    assert card["skills"][0]["id"] == "generate_ad_banner"
    assert card["supportedInterfaces"][0]["protocolBinding"] == "HTTP+JSON"
```

- [ ] **Step 2: Add failing A2A send-message and task retrieval tests**

Append to `tests/test_api.py`:

```python
def test_a2a_send_message_generates_completed_task(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    request = {
        "message": {
            "role": "ROLE_USER",
            "messageId": "msg-1",
            "parts": [{"data": base_payload()}],
        }
    }

    response = client.post(
        "/message:send",
        json=request,
        headers={"content-type": "application/a2a+json"},
    )

    assert response.status_code == 200
    body = response.json()
    task = body["task"]
    assert task["status"]["state"] == "TASK_STATE_COMPLETED"
    artifact_payload = task["artifacts"][0]["parts"][0]["data"]
    assert artifact_payload["copy_backend"] == "mock"
    assert artifact_payload["image_backend"] == "mock"

    task_response = client.get(f"/tasks/{task['id']}")
    assert task_response.status_code == 200
    assert task_response.json()["id"] == task["id"]


def test_a2a_send_message_rejects_missing_data_part() -> None:
    response = client.post(
        "/message:send",
        json={
            "message": {
                "role": "ROLE_USER",
                "messageId": "msg-2",
                "parts": [{"text": "make me an ad"}],
            }
        },
        headers={"content-type": "application/a2a+json"},
    )

    assert response.status_code == 400
    assert "application/json data part" in response.json()["detail"]


def test_a2a_get_missing_task_returns_404() -> None:
    response = client.get("/tasks/task-missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "A2A task not found"
```

- [ ] **Step 3: Run failing A2A API tests**

Run:

```bash
pytest tests/test_api.py::test_a2a_agent_card \
  tests/test_api.py::test_a2a_send_message_generates_completed_task \
  tests/test_api.py::test_a2a_send_message_rejects_missing_data_part \
  tests/test_api.py::test_a2a_get_missing_task_returns_404 -q
```

Expected:

```text
4 failed
```

The failures should be `404 Not Found` before routes exist.

- [ ] **Step 4: Add A2A imports and task store**

Modify `api/main.py` imports:

```python
from typing import Any

from dessert_ad_studio.a2a import (
    A2AInputError,
    A2ATaskStore,
    build_agent_card,
    completed_generation_task,
    extract_generation_request,
)
```

Add near the metrics globals:

```python
_A2A_TASKS = A2ATaskStore()
```

- [ ] **Step 5: Add helper for workflow dependencies**

Add this helper in `api/main.py` above the route definitions:

```python
def build_workflow_dependencies() -> GenerationWorkflowDependencies:
    return GenerationWorkflowDependencies(
        template_scorer=get_template_scorer(),
        copy_backend=get_copy_backend(),
        image_backend=get_image_backend(),
        product_analyzer=get_product_analyzer(),
        log_path=Path(os.getenv("GENERATION_LOG_PATH", "logs/generations.jsonl")),
    )
```

Update `/generate` from Task 2 to call `build_workflow_dependencies()` so A2A and REST use the same dependency assembly:

```python
    dependencies = build_workflow_dependencies()
```

- [ ] **Step 6: Add Agent Card and A2A task endpoints**

Add to `api/main.py`:

```python
@app.get("/.well-known/agent-card.json")
def a2a_agent_card(request: Request) -> dict[str, Any]:
    return build_agent_card(base_url=str(request.base_url).rstrip("/"))


@app.post("/message:send")
def a2a_send_message(payload: dict[str, Any]) -> dict[str, Any]:
    message = payload.get("message")
    if not isinstance(message, dict):
        raise HTTPException(status_code=400, detail="A2A request must include message")

    try:
        generation_request = extract_generation_request(message)
    except A2AInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    dependencies = build_workflow_dependencies()
    try:
        output = run_generation_workflow(generation_request, dependencies)
    except ReferenceImageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AdBackendError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    task = completed_generation_task(
        output.response,
        message_id=message.get("messageId"),
        context_id=message.get("contextId"),
    )
    _A2A_TASKS.save(task)
    return {"task": task}


@app.get("/tasks/{task_id}")
def a2a_get_task(task_id: str) -> dict[str, Any]:
    task = _A2A_TASKS.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="A2A task not found")
    return task
```

- [ ] **Step 7: Run A2A API tests**

Run:

```bash
pytest tests/test_api.py::test_a2a_agent_card \
  tests/test_api.py::test_a2a_send_message_generates_completed_task \
  tests/test_api.py::test_a2a_send_message_rejects_missing_data_part \
  tests/test_api.py::test_a2a_get_missing_task_returns_404 -q
```

Expected:

```text
4 passed
```

- [ ] **Step 8: Run full API tests**

Run:

```bash
pytest tests/test_api.py -q
```

Expected:

```text
all tests pass
```

- [ ] **Step 9: Commit A2A endpoints**

Run:

```bash
git add api/main.py tests/test_api.py
git commit -m "Expose A2A ad generation spike"
```

Expected:

```text
[main <hash>] Expose A2A ad generation spike
```

---

### Task 5: Add A2A Smoke Script and README Notes

**Files:**
- Create: `scripts/a2a_smoke.py`
- Modify: `README.md`

- [ ] **Step 1: Add smoke script**

Create `scripts/a2a_smoke.py`:

```python
from __future__ import annotations

import argparse
import sys

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test the Dessert Ad Studio A2A spike.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    card_response = httpx.get(f"{base_url}/.well-known/agent-card.json", timeout=10)
    card_response.raise_for_status()
    card = card_response.json()
    print(f"agent={card['name']} skill={card['skills'][0]['id']}")

    payload = {
        "message": {
            "role": "ROLE_USER",
            "messageId": "smoke-msg-1",
            "parts": [
                {
                    "data": {
                        "campaign_purpose": "new_menu",
                        "product_name": "말차 푸딩",
                        "tone": "clean",
                        "template_hint": "minimal_premium",
                        "price_text": "5,500원",
                        "user_constraints": "깔끔한 프리미엄 느낌",
                    }
                }
            ],
        }
    }
    send_response = httpx.post(
        f"{base_url}/message:send",
        json=payload,
        headers={"content-type": "application/a2a+json"},
        timeout=60,
    )
    send_response.raise_for_status()
    task = send_response.json()["task"]
    print(f"task={task['id']} state={task['status']['state']}")

    task_response = httpx.get(f"{base_url}/tasks/{task['id']}", timeout=10)
    task_response.raise_for_status()
    artifact = task_response.json()["artifacts"][0]["parts"][0]["data"]
    print(f"image_path={artifact['image_path']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Add README section**

Add this section to `README.md` after the FastAPI quick start section:

```markdown
## A2A Interoperability Spike

The API exposes a narrow A2A-compatible surface for portfolio interoperability evidence.
It does not replace the normal REST API or the Streamlit UI.

Discovery:

```text
GET /.well-known/agent-card.json
```

Task execution:

```text
POST /message:send
Content-Type: application/a2a+json
```

The supported skill is `generate_ad_banner`. The first message part must contain a JSON
`data` object using the same fields as `POST /generate`.

Run a local smoke test after starting the API:

```bash
python scripts/a2a_smoke.py --base-url http://127.0.0.1:8000
```

Use A2A when another agent needs to discover and call Dessert Ad Studio as a remote
agent capability. Use the normal REST API for app/frontend calls. FastMCP remains a
future tool-server layer for exposing lower-level typed tools.
```
```

When inserting this section, remove the extra final triple backtick from the snippet above. The README must render with balanced code fences.

- [ ] **Step 3: Run smoke script help**

Run:

```bash
python scripts/a2a_smoke.py --help
```

Expected:

```text
usage: a2a_smoke.py [-h] [--base-url BASE_URL]
```

- [ ] **Step 4: Run focused lint on new script**

Run:

```bash
ruff check scripts/a2a_smoke.py
```

Expected:

```text
All checks passed!
```

- [ ] **Step 5: Commit docs and smoke script**

Run:

```bash
git add README.md scripts/a2a_smoke.py
git commit -m "Document A2A smoke path"
```

Expected:

```text
[main <hash>] Document A2A smoke path
```

---

### Task 6: Final Verification

**Files:**
- No new files

- [ ] **Step 1: Run unit/API tests**

Run:

```bash
pytest -q
```

Expected:

```text
all tests pass
```

- [ ] **Step 2: Run linter**

Run:

```bash
ruff check .
```

Expected:

```text
All checks passed!
```

- [ ] **Step 3: Start API for manual A2A smoke**

Run:

```bash
uvicorn api.main:app --port 8000
```

Expected:

```text
Uvicorn running on http://127.0.0.1:8000
```

- [ ] **Step 4: Run A2A smoke in a second shell**

Run:

```bash
python scripts/a2a_smoke.py --base-url http://127.0.0.1:8000
```

Expected:

```text
agent=Dessert Ad Studio Agent skill=generate_ad_banner
task=task-... state=TASK_STATE_COMPLETED
image_path=...
```

- [ ] **Step 5: Stop API server**

Stop the `uvicorn` process with `Ctrl-C`.

- [ ] **Step 6: Review git status**

Run:

```bash
git status --short
```

Expected:

```text
?? .playwright-cli/
?? .serena/
?? .superpowers/
?? "[AI] 고급프로젝트 가이드 650fc8105e0d838e920181b4c15e7593.md"
```

Only the known pre-existing untracked files should remain.
