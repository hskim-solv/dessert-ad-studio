from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dessert_ad_studio.agentic_rag import (  # noqa: E402
    build_agentic_rag_graph,
    build_agentic_rag_initial_state,
)
from dessert_ad_studio.observability import InMemoryWorkflowTracer  # noqa: E402
from dessert_ad_studio.schemas import GenerationRequest  # noqa: E402


DEFAULT_OUTPUT_PATH = Path("docs/evidence/agentic-rag-trace-summary.json")


def build_agentic_rag_trace_summary(*, evidence_date: str) -> dict[str, Any]:
    tracer = InMemoryWorkflowTracer()

    def worker_executor(_state: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "succeeded",
            "copy_backend": "mock",
            "image_backend": "mock",
            "copy_option_count": 3,
            "used_reference": False,
            "elapsed_ms": 21.0,
            "workflow_trace_steps": ["rank_templates", "generate_copy", "generate_image"],
        }

    graph = build_agentic_rag_graph(
        worker_executor=worker_executor,
        workflow_tracer=tracer,
    )
    state = build_agentic_rag_initial_state(
        GenerationRequest(
            campaign_purpose="new_menu",
            product_name="비공개 말차 푸딩",
            tone="premium",
            template_hint="minimal_premium",
            user_constraints="VIP 고객에게만 보일 문구",
        ),
        requires_paid_provider=False,
        estimated_cost_usd=0.0,
        approval_cost_threshold_usd=0.10,
    )
    result = graph.invoke(state)
    records = tracer.records()
    return {
        "agentic_rag_trace_smoke": "passed",
        "scope": "local_in_memory_openinference_trace_no_paid_api_call",
        "evidence_date": evidence_date,
        "final_status": result["status"],
        "final_next_action": result["next_action"],
        "span_names": [record.name for record in records],
        "span_kinds": [record.kind for record in records],
        "span_count": len(records),
        "redacted_attribute_keys": sorted(
            {
                key
                for record in records
                for key in record.attributes
                if key.startswith("agentic_rag.")
            }
        ),
        "raw_inputs_committed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build local Agentic RAG OpenInference trace evidence.",
        allow_abbrev=False,
    )
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()

    summary = build_agentic_rag_trace_summary(evidence_date=args.date)
    payload = json.dumps(summary, ensure_ascii=False, indent=2)
    print(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(payload + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
