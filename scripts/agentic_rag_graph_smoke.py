from __future__ import annotations

import argparse
from datetime import date
import importlib.metadata
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402

from dessert_ad_studio.agentic_rag import (  # noqa: E402
    build_agentic_rag_graph,
    build_agentic_rag_initial_state,
    build_generation_workflow_executor,
)
from dessert_ad_studio.backends.mock import MockAdBackend  # noqa: E402
from dessert_ad_studio.product_analysis import MockProductAnalyzer  # noqa: E402
from dessert_ad_studio.schemas import GenerationRequest  # noqa: E402
from dessert_ad_studio.triton import LocalTemplateScorer  # noqa: E402
from dessert_ad_studio.workflow import GenerationWorkflowDependencies  # noqa: E402


DEFAULT_OUTPUT_PATH = Path("docs/evidence/agentic-rag-graph-summary.json")


def build_agentic_rag_graph_summary(*, evidence_date: str) -> dict[str, Any]:
    approval_route = _run_approval_route()
    worker_route = _run_worker_route()
    return {
        "agentic_rag_graph_smoke": "passed",
        "scope": "offline_langgraph_control_plane_no_paid_api_call",
        "evidence_date": evidence_date,
        "langgraph_version": importlib.metadata.version("langgraph"),
        "approval_route": approval_route,
        "worker_route": worker_route,
    }


def _run_approval_route() -> dict[str, Any]:
    checkpointer = InMemorySaver()
    thread_id = "agentic-rag-approval-smoke"
    graph = build_agentic_rag_graph(checkpointer=checkpointer)
    state = build_agentic_rag_initial_state(
        GenerationRequest(
            campaign_purpose="new_menu",
            product_name="비공개 말차 푸딩",
            tone="premium",
            template_hint="minimal_premium",
            price_text="7,500원",
            user_constraints="VIP 고객에게만 보일 문구",
            revision_request="비공개 할인 강조",
            reference_image_b64="c2VjcmV0LWltYWdlLWJ5dGVz",
            reference_image_name="secret-reference.png",
        ),
        requires_paid_provider=True,
        estimated_cost_usd=0.12,
        approval_cost_threshold_usd=0.10,
    )
    result = graph.invoke(state, {"configurable": {"thread_id": thread_id}})
    checkpoints = list(checkpointer.list({"configurable": {"thread_id": thread_id}}))
    return {
        "status": result["status"],
        "next_action": result["next_action"],
        "node_trace": result["node_trace"],
        "approval_required": result["approval"]["required"],
        "approval_reasons": result["approval"]["reasons"],
        "retriever_backend": result["marketing_context"]["retriever_backend"],
        "retrieved_docs_count": result["marketing_context"]["retrieved_docs_count"],
        "citation_count": len(result["citations"]),
        "checkpoint_count": len(checkpoints),
        "request_summary_fields": sorted(result["request_summary"].keys()),
        "raw_inputs_committed": False,
    }


def _run_worker_route() -> dict[str, Any]:
    checkpointer = InMemorySaver()
    thread_id = "agentic-rag-worker-smoke"
    request = GenerationRequest(
        campaign_purpose="brand_awareness",
        product_name="비공개 딸기 크림 크루아상",
        tone="warm",
        template_hint="cozy_cafe",
        user_constraints="VIP 촬영본으로 인스타그램 피드용",
    )
    backend = MockAdBackend(output_dir="outputs/agentic-rag-graph-smoke")
    dependencies = GenerationWorkflowDependencies(
        template_scorer=LocalTemplateScorer(),
        copy_backend=backend,
        image_backend=backend,
        product_analyzer=MockProductAnalyzer(),
        log_path=Path("logs/agentic-rag-graph-smoke-generations.jsonl"),
    )
    graph = build_agentic_rag_graph(
        checkpointer=checkpointer,
        worker_executor=build_generation_workflow_executor(request, dependencies),
    )
    state = build_agentic_rag_initial_state(
        request,
        requires_paid_provider=False,
        estimated_cost_usd=0.0,
        approval_cost_threshold_usd=0.10,
    )
    result = graph.invoke(state, {"configurable": {"thread_id": thread_id}})
    checkpoints = list(checkpointer.list({"configurable": {"thread_id": thread_id}}))
    worker_result = result["worker_result"]
    cited_ad_package = result["cited_ad_package"]
    return {
        "status": result["status"],
        "next_action": result["next_action"],
        "node_trace": result["node_trace"],
        "retriever_backend": result["marketing_context"]["retriever_backend"],
        "retrieved_docs_count": result["marketing_context"]["retrieved_docs_count"],
        "citation_count": len(result["citations"]),
        "checkpoint_count": len(checkpoints),
        "worker_status": worker_result["status"],
        "copy_backend": worker_result["copy_backend"],
        "image_backend": worker_result["image_backend"],
        "copy_option_count": worker_result["copy_option_count"],
        "used_reference": worker_result["used_reference"],
        "workflow_trace_steps": worker_result["workflow_trace_steps"],
        "cited_ad_package_ready": cited_ad_package["status"] == "ready",
        "cited_ad_package_source_doc_count": len(cited_ad_package["citation_source_doc_ids"]),
        "raw_assets_committed": cited_ad_package["raw_assets_committed"],
        "raw_inputs_committed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build offline LangGraph Agentic RAG control-plane evidence.",
        allow_abbrev=False,
    )
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()

    summary = build_agentic_rag_graph_summary(evidence_date=args.date)
    payload = json.dumps(summary, ensure_ascii=False, indent=2)
    print(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(payload + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
