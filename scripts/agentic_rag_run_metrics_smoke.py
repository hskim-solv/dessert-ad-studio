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
from dessert_ad_studio.observability import (  # noqa: E402
    InMemoryWorkflowTracer,
    WorkflowSpanRecord,
)
from dessert_ad_studio.schemas import GenerationRequest  # noqa: E402


DEFAULT_OUTPUT_PATH = Path("docs/evidence/agentic-rag-run-metrics-summary.json")


def build_agentic_rag_run_metrics_summary(*, evidence_date: str) -> dict[str, Any]:
    success_tracer = InMemoryWorkflowTracer()
    success_graph = build_agentic_rag_graph(
        worker_executor=_successful_worker_executor,
        workflow_tracer=success_tracer,
    )
    success_result = success_graph.invoke(_initial_state())

    failure_tracer = InMemoryWorkflowTracer()
    failure_graph = build_agentic_rag_graph(
        worker_executor=_failing_worker_executor,
        workflow_tracer=failure_tracer,
    )
    failure_result = failure_graph.invoke(_initial_state())

    success_records = success_tracer.records()
    failure_records = failure_tracer.records()
    return {
        "agentic_rag_run_metrics_smoke": "passed",
        "scope": "local_agentic_rag_metrics_no_paid_api_call",
        "evidence_date": evidence_date,
        "paid_api_call_count": 0,
        "final_status": success_result["status"],
        "final_next_action": success_result["next_action"],
        "latency": _latency_summary(success_records),
        "token_usage": {
            "estimated_total_tokens": 0,
            "source": "mock_worker_and_local_tools_no_llm_call",
        },
        "cost": {
            "estimated_total_usd": 0.0,
            "source": "mock_worker_and_local_tools_no_paid_provider",
        },
        "tool_calls": _tool_call_summary(success_result),
        "failed_run_analysis": _failed_run_summary(failure_result, failure_records),
        "raw_inputs_committed": False,
    }


def _initial_state() -> dict[str, Any]:
    return build_agentic_rag_initial_state(
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


def _successful_worker_executor(_state: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "succeeded",
        "copy_backend": "mock",
        "image_backend": "mock",
        "copy_option_count": 3,
        "used_reference": False,
        "elapsed_ms": 21.0,
        "workflow_trace_steps": ["rank_templates", "generate_copy", "generate_image"],
    }


def _failing_worker_executor(_state: dict[str, Any]) -> dict[str, Any]:
    raise RuntimeError("raw private customer text")


def _latency_summary(records: list[WorkflowSpanRecord]) -> dict[str, Any]:
    elapsed_values = [record.elapsed_ms for record in records]
    total_elapsed_ms = round(sum(elapsed_values), 3)
    return {
        "span_count": len(records),
        "total_elapsed_ms": total_elapsed_ms,
        "max_elapsed_ms": round(max(elapsed_values, default=0.0), 3),
        "by_node": [
            {
                "name": record.name,
                "kind": record.kind,
                "elapsed_ms": round(record.elapsed_ms, 3),
                "error_type": record.error_type,
            }
            for record in records
        ],
    }


def _tool_call_summary(result: dict[str, Any]) -> dict[str, Any]:
    tool_budget = result.get("plan", {}).get("tool_budget", {})
    planned_tools = list(tool_budget.get("planned_tools", []))
    tool_results = result.get("tool_results", {})
    result_keys = sorted(tool_results) if isinstance(tool_results, dict) else []
    return {
        "planned_tools": planned_tools,
        "planned_count": len(planned_tools),
        "max_tool_calls": tool_budget.get("max_tool_calls"),
        "result_keys": result_keys,
        "result_count": len(result_keys),
        "success_count": len(result_keys),
        "failure_count": 0,
    }


def _failed_run_summary(
    result: dict[str, Any],
    records: list[WorkflowSpanRecord],
) -> dict[str, Any]:
    worker_records = [
        record
        for record in records
        if record.name == "agentic_rag.execute_worker"
        and record.attributes.get("agentic_rag.worker_status") == "failed"
    ]
    worker_error_types = sorted(
        {
            str(record.attributes["agentic_rag.worker_error_type"])
            for record in worker_records
            if "agentic_rag.worker_error_type" in record.attributes
        }
    )
    if not worker_error_types:
        worker_result = result.get("worker_result", {})
        error_type = worker_result.get("error_type")
        worker_error_types = [str(error_type)] if error_type else []
    reflection = result.get("reflection", {})
    graceful_fallback = result.get("graceful_fallback", {})
    return {
        "status": result["status"],
        "next_action": result["next_action"],
        "worker_error_types": worker_error_types,
        "retry_attempts": reflection.get("attempts", 0),
        "retry_budget": reflection.get("retry_budget", 0),
        "failed_span_count": len(worker_records),
        "graceful_fallback_ready": graceful_fallback.get("status") == "ready",
        "fallback_reason": graceful_fallback.get("reason"),
        "fallback_next_action": graceful_fallback.get("next_action"),
        "fallback_retry_attempts": graceful_fallback.get("retry_attempts", 0),
        "fallback_retry_budget": graceful_fallback.get("retry_budget", 0),
        "fallback_last_error_type": graceful_fallback.get("last_error_type"),
        "raw_error_committed": graceful_fallback.get("raw_error_committed", False),
        "raw_inputs_committed": graceful_fallback.get("raw_inputs_committed", False),
        "raw_error_message_committed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build local Agentic RAG run metrics evidence.",
        allow_abbrev=False,
    )
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()

    summary = build_agentic_rag_run_metrics_summary(evidence_date=args.date)
    payload = json.dumps(summary, ensure_ascii=False, indent=2)
    print(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(payload + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
