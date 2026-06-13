# OTLP Phoenix Export Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add optional OTLP HTTP trace export and local Phoenix Docker Compose evidence for the existing OpenTelemetry/OpenInference workflow spans.

**Architecture:** Keep the current `build_workflow_tracer()` entrypoint and extend only the `WORKFLOW_TRACING=otel` path. `WORKFLOW_TRACE_EXPORT=console` remains the default, `WORKFLOW_TRACE_EXPORT=otlp` adds an OTLP HTTP exporter, and Phoenix is enabled only through an optional compose override.

**Tech Stack:** Python 3.11, OpenTelemetry Python SDK, `opentelemetry-exporter-otlp-proto-http`, OpenInference semantic conventions, Docker Compose, Arize Phoenix Docker image.

---

## File Structure

- Modify `pyproject.toml`
  - Add the OTLP HTTP exporter package.
- Modify `src/dessert_ad_studio/observability.py`
  - Add OTLP endpoint resolution and exporter construction.
- Modify `tests/test_observability.py`
  - Add focused tests for OTLP mode and endpoint resolution.
- Create `scripts/otel_trace_smoke.py`
  - Run one mock workflow under the configured workflow tracer.
- Create `tests/test_otel_trace_smoke.py`
  - Verify the smoke script runs without Phoenix when console export is used.
- Create `docker-compose.agentops.yml`
  - Optional Phoenix service and API trace export env overrides.
- Modify `README.md`
  - Document local console, OTLP/Phoenix, and compose commands without claiming hosted readiness.

---

### Task 1: OTLP Exporter Plumbing

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/dessert_ad_studio/observability.py`
- Modify: `tests/test_observability.py`

- [ ] **Step 1: Add failing tests for endpoint resolution and OTLP mode**

Append to `tests/test_observability.py`:

```python
import pytest

from dessert_ad_studio.observability import (
    OpenInferenceWorkflowTracer,
    build_workflow_tracer,
    resolve_otlp_trace_endpoint,
)


def test_resolve_otlp_trace_endpoint_prefers_trace_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://collector:4318/custom")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4318")

    assert resolve_otlp_trace_endpoint() == "http://collector:4318/custom"


def test_resolve_otlp_trace_endpoint_appends_trace_path_to_base_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4318")

    assert resolve_otlp_trace_endpoint() == "http://collector:4318/v1/traces"


def test_resolve_otlp_trace_endpoint_defaults_to_local_phoenix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

    assert resolve_otlp_trace_endpoint() == "http://localhost:6006/v1/traces"


def test_build_workflow_tracer_supports_otlp_export(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WORKFLOW_TRACE_EXPORT", "otlp")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://collector:4318/v1/traces")

    tracer = build_workflow_tracer("otel")

    assert isinstance(tracer, OpenInferenceWorkflowTracer)


def test_build_workflow_tracer_rejects_unknown_export(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WORKFLOW_TRACE_EXPORT", "zipkin")

    with pytest.raises(ValueError, match="unsupported workflow trace export"):
        build_workflow_tracer("otel")
```

- [ ] **Step 2: Run failing observability tests**

Run:

```bash
.venv/bin/pytest tests/test_observability.py -q
```

Expected: fail because `resolve_otlp_trace_endpoint` is missing and `otlp` export is unsupported.

- [ ] **Step 3: Add the OTLP HTTP exporter dependency**

In `pyproject.toml`, add this runtime dependency near the other OpenTelemetry packages:

```toml
  "opentelemetry-exporter-otlp-proto-http>=1.38",
```

Then install:

```bash
.venv/bin/pip install -e ".[dev]"
```

Expected: editable install succeeds.

- [ ] **Step 4: Implement endpoint resolution and OTLP exporter**

Modify `src/dessert_ad_studio/observability.py`:

```python
_OTLP_HTTP_MISSING_MESSAGE = (
    "WORKFLOW_TRACE_EXPORT=otlp requires opentelemetry-exporter-otlp-proto-http. "
    "Install project dependencies with `.venv/bin/pip install -e \".[dev]\"`."
)


def resolve_otlp_trace_endpoint() -> str:
    trace_endpoint = os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "").strip()
    if trace_endpoint:
        return trace_endpoint

    base_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if not base_endpoint:
        return "http://localhost:6006/v1/traces"
    return _append_otlp_trace_path(base_endpoint)


def _append_otlp_trace_path(endpoint: str) -> str:
    normalized = endpoint.rstrip("/")
    if normalized.endswith("/v1/traces"):
        return normalized
    return f"{normalized}/v1/traces"
```

Inside `_build_otel_workflow_tracer()`, keep console behavior and add:

```python
    elif trace_export == "otlp":
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        except ImportError as exc:
            raise RuntimeError(_OTLP_HTTP_MISSING_MESSAGE) from exc
        provider.add_span_processor(
            SimpleSpanProcessor(
                OTLPSpanExporter(endpoint=resolve_otlp_trace_endpoint())
            )
        )
```

- [ ] **Step 5: Run focused tests and lint**

Run:

```bash
.venv/bin/pytest tests/test_observability.py -q
.venv/bin/ruff check src/dessert_ad_studio/observability.py tests/test_observability.py
```

Expected: all observability tests pass and ruff reports no issues.

- [ ] **Step 6: Commit Task 1**

```bash
git add pyproject.toml src/dessert_ad_studio/observability.py tests/test_observability.py
git commit -m "Add OTLP workflow trace export"
```

---

### Task 2: OTEL Trace Smoke Script

**Files:**
- Create: `scripts/otel_trace_smoke.py`
- Create: `tests/test_otel_trace_smoke.py`

- [ ] **Step 1: Write failing smoke script test**

Create `tests/test_otel_trace_smoke.py`:

```python
import os
import subprocess
import sys


def test_otel_trace_smoke_runs_with_console_export(tmp_path) -> None:
    env = {
        **os.environ,
        "WORKFLOW_TRACING": "otel",
        "WORKFLOW_TRACE_EXPORT": "console",
        "OUTPUT_DIR": str(tmp_path / "outputs"),
        "GENERATION_LOG_PATH": str(tmp_path / "generations.jsonl"),
    }

    result = subprocess.run(
        [sys.executable, "scripts/otel_trace_smoke.py"],
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert result.returncode == 0
    assert "trace_smoke=passed" in result.stdout
    assert "export=console" in result.stdout
```

- [ ] **Step 2: Run failing smoke test**

Run:

```bash
.venv/bin/pytest tests/test_otel_trace_smoke.py -q
```

Expected: fail because `scripts/otel_trace_smoke.py` does not exist.

- [ ] **Step 3: Implement smoke script**

Create `scripts/otel_trace_smoke.py`:

```python
from __future__ import annotations

import os
from pathlib import Path

from dessert_ad_studio.backends.mock import MockAdBackend
from dessert_ad_studio.observability import build_workflow_tracer, resolve_otlp_trace_endpoint
from dessert_ad_studio.product_analysis import MockProductAnalyzer
from dessert_ad_studio.schemas import GenerationRequest
from dessert_ad_studio.triton import LocalTemplateScorer
from dessert_ad_studio.workflow import GenerationWorkflowDependencies, run_generation_workflow


def main() -> int:
    os.environ.setdefault("WORKFLOW_TRACING", "otel")
    os.environ.setdefault("WORKFLOW_TRACE_EXPORT", "console")

    output_dir = Path(os.getenv("OUTPUT_DIR", "outputs/otel-smoke"))
    log_path = Path(os.getenv("GENERATION_LOG_PATH", "logs/otel-smoke-generations.jsonl"))
    backend = MockAdBackend(output_dir=output_dir)
    request = GenerationRequest(
        campaign_purpose="new_menu",
        product_name="말차 푸딩",
        tone="clean",
        template_hint="minimal_premium",
        price_text="5,500원",
        user_constraints="OTLP trace smoke",
    )
    output = run_generation_workflow(
        request,
        GenerationWorkflowDependencies(
            template_scorer=LocalTemplateScorer(),
            copy_backend=backend,
            image_backend=backend,
            product_analyzer=MockProductAnalyzer(),
            log_path=log_path,
            workflow_tracer=build_workflow_tracer("otel"),
        ),
    )

    export_mode = os.getenv("WORKFLOW_TRACE_EXPORT", "console")
    endpoint = resolve_otlp_trace_endpoint() if export_mode == "otlp" else "local-console"
    print(
        "trace_smoke=passed "
        f"export={export_mode} "
        f"endpoint={endpoint} "
        f"steps={len(output.trace)} "
        f"image_path={output.response.image_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run smoke test and script**

Run:

```bash
.venv/bin/pytest tests/test_otel_trace_smoke.py -q
WORKFLOW_TRACING=otel WORKFLOW_TRACE_EXPORT=console .venv/bin/python scripts/otel_trace_smoke.py
.venv/bin/ruff check scripts/otel_trace_smoke.py tests/test_otel_trace_smoke.py
```

Expected: test passes, smoke script exits `0`, ruff passes.

- [ ] **Step 5: Commit Task 2**

```bash
git add scripts/otel_trace_smoke.py tests/test_otel_trace_smoke.py
git commit -m "Add OTEL trace smoke script"
```

---

### Task 3: Phoenix Compose and README Evidence

**Files:**
- Create: `docker-compose.agentops.yml`
- Modify: `README.md`

- [ ] **Step 1: Add optional Phoenix compose override**

Create `docker-compose.agentops.yml`:

```yaml
services:
  phoenix:
    image: arizephoenix/phoenix:latest
    ports:
      - "6006:6006"
      - "4317:4317"
    environment:
      PHOENIX_WORKING_DIR: /phoenix_data
    volumes:
      - phoenix-data:/phoenix_data

  api:
    environment:
      WORKFLOW_TRACING: otel
      WORKFLOW_TRACE_EXPORT: otlp
      OTEL_EXPORTER_OTLP_TRACES_ENDPOINT: http://phoenix:6006/v1/traces
      OTEL_SERVICE_NAME: dessert-ad-studio-api
    depends_on:
      phoenix:
        condition: service_started

volumes:
  phoenix-data:
```

- [ ] **Step 2: Update README AgentOps Evidence**

Modify the existing `## AgentOps Evidence` section in `README.md` to include:

```markdown
Run a local console trace smoke:

```bash
WORKFLOW_TRACING=otel WORKFLOW_TRACE_EXPORT=console python scripts/otel_trace_smoke.py
```

Run Phoenix locally through the optional compose override:

```bash
docker compose -f docker-compose.yml -f docker-compose.agentops.yml up --build
```

Open:

```text
Phoenix: http://localhost:6006
```

The override sends API workflow spans to Phoenix through OTLP HTTP at
`http://phoenix:6006/v1/traces`. Phoenix remains optional; normal local evals,
REST calls, and Streamlit usage do not require it.
```

Keep the existing deterministic eval command:

```bash
python scripts/eval_demo_samples.py
```

- [ ] **Step 3: Validate compose syntax and docs commands**

Run:

```bash
docker compose -f docker-compose.yml -f docker-compose.agentops.yml config >/tmp/dessert-agentops-compose.yml
WORKFLOW_TRACING=otel WORKFLOW_TRACE_EXPORT=console .venv/bin/python scripts/otel_trace_smoke.py
.venv/bin/python scripts/eval_demo_samples.py
```

Expected: compose config command succeeds, smoke script exits `0`, eval script exits `0`.

- [ ] **Step 4: Commit Task 3**

```bash
git add docker-compose.agentops.yml README.md
git commit -m "Document Phoenix trace export compose"
```

---

### Task 4: Final Verification and Review

**Files:**
- Review all touched files.

- [ ] **Step 1: Run full verification**

Run:

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/python scripts/eval_demo_samples.py
WORKFLOW_TRACING=otel WORKFLOW_TRACE_EXPORT=console .venv/bin/python scripts/otel_trace_smoke.py
docker compose -f docker-compose.yml -f docker-compose.agentops.yml config >/tmp/dessert-agentops-compose.yml
```

Expected:

- pytest passes.
- ruff passes.
- eval script exits `0`.
- trace smoke exits `0`.
- compose config renders successfully.

- [ ] **Step 2: Inspect worktree**

Run:

```bash
git status --short
git diff --check
git log --oneline -8
```

Expected: only unrelated pre-existing untracked files remain.

- [ ] **Step 3: Spec compliance review**

Check against `docs/superpowers/specs/2026-06-13-otlp-phoenix-export-design.md`:

- Defaults remain safe.
- Console export still works.
- `WORKFLOW_TRACE_EXPORT=otlp` uses OTLP HTTP exporter.
- Phoenix is optional via compose override.
- README does not overclaim hosted readiness.

- [ ] **Step 4: Code quality review**

Check:

- No global tracer provider mutation.
- No prompt/image bytes exported.
- Endpoint resolution is predictable.
- Smoke script does not require Phoenix in console mode.
- Compose override does not change normal `docker compose up --build`.

- [ ] **Step 5: Commit review fixes if needed**

If review fixes are needed:

```bash
git add pyproject.toml src/dessert_ad_studio/observability.py tests/test_observability.py scripts/otel_trace_smoke.py tests/test_otel_trace_smoke.py docker-compose.agentops.yml README.md
git commit -m "Harden OTLP Phoenix trace export"
```

If no fixes are needed, no additional commit is required.
