from __future__ import annotations

from contextlib import nullcontext, redirect_stdout
from io import StringIO
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

    export_mode = os.getenv("WORKFLOW_TRACE_EXPORT", "console").strip().lower()
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
    stdout_context = redirect_stdout(StringIO()) if export_mode == "console" else nullcontext()
    with stdout_context:
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
