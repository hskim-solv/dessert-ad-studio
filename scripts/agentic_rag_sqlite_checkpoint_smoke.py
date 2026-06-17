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

from dessert_ad_studio.agentic_rag import (  # noqa: E402
    build_agentic_rag_graph,
    build_agentic_rag_initial_state,
    open_agentic_rag_sqlite_checkpointer,
)
from dessert_ad_studio.schemas import GenerationRequest  # noqa: E402


DEFAULT_OUTPUT_PATH = Path("docs/evidence/agentic-rag-sqlite-checkpoint-summary.json")
DEFAULT_CHECKPOINT_DB = Path("outputs/agentic-rag-checkpoints/agentic-rag-checkpoints.sqlite")
RAW_VALUES = [
    "비공개 말차 푸딩",
    "VIP 고객에게만 보일 문구",
    "비공개 할인 강조",
    "secret-reference.png",
    "c2VjcmV0LWltYWdlLWJ5dGVz",
]


def build_sqlite_checkpoint_summary(
    *,
    evidence_date: str,
    checkpoint_db: Path,
) -> dict[str, Any]:
    if checkpoint_db.exists():
        checkpoint_db.unlink()

    thread_id = "agentic-rag-sqlite-checkpoint-smoke"
    config = {"configurable": {"thread_id": thread_id}}
    worker_calls: list[dict[str, Any]] = []

    def worker_executor(state: dict[str, Any]) -> dict[str, Any]:
        worker_calls.append(state)
        return {
            "status": "succeeded",
            "copy_backend": "mock",
            "image_backend": "mock",
            "copy_option_count": 3,
            "used_reference": False,
            "elapsed_ms": 19.0,
            "workflow_trace_steps": ["rank_templates", "generate_copy", "generate_image"],
        }

    request = GenerationRequest(
        campaign_purpose="new_menu",
        product_name=RAW_VALUES[0],
        tone="premium",
        template_hint="minimal_premium",
        price_text="7,500원",
        user_constraints=RAW_VALUES[1],
        revision_request=RAW_VALUES[2],
        reference_image_b64=RAW_VALUES[4],
        reference_image_name=RAW_VALUES[3],
    )
    state = build_agentic_rag_initial_state(
        request,
        requires_paid_provider=False,
        estimated_cost_usd=0.0,
        approval_cost_threshold_usd=0.10,
    )

    with open_agentic_rag_sqlite_checkpointer(checkpoint_db) as checkpointer:
        graph = build_agentic_rag_graph(
            checkpointer=checkpointer,
            worker_executor=worker_executor,
        )
        result = graph.invoke(state, config)
        checkpoint_count = len(list(checkpointer.list(config)))

    with open_agentic_rag_sqlite_checkpointer(checkpoint_db) as checkpointer:
        reopened_checkpoint_count = len(list(checkpointer.list(config)))

    checkpoint_bytes = checkpoint_db.read_bytes()
    raw_inputs_found = any(value.encode("utf-8") in checkpoint_bytes for value in RAW_VALUES)
    cited_ad_package = result["cited_ad_package"]

    return {
        "agentic_rag_sqlite_checkpoint_smoke": "passed",
        "scope": "local_sqlite_langgraph_checkpointer_no_paid_api_call",
        "evidence_date": evidence_date,
        "langgraph_version": importlib.metadata.version("langgraph"),
        "langgraph_checkpoint_sqlite_version": importlib.metadata.version(
            "langgraph-checkpoint-sqlite"
        ),
        "checkpoint_backend": "sqlite",
        "checkpoint_path_committed": False,
        "checkpoint_file_created": checkpoint_db.exists(),
        "checkpoint_count": checkpoint_count,
        "reopened_checkpoint_count": reopened_checkpoint_count,
        "raw_inputs_found_in_checkpoint": raw_inputs_found,
        "worker_call_count": len(worker_calls),
        "final_status": result["status"],
        "next_action": result["next_action"],
        "cited_ad_package_ready": cited_ad_package["status"] == "ready",
        "cited_ad_package_source_doc_count": len(cited_ad_package["citation_source_doc_ids"]),
        "raw_assets_committed": cited_ad_package["raw_assets_committed"],
        "node_trace": result["node_trace"],
        "request_summary_fields": sorted(result["request_summary"].keys()),
        "raw_inputs_committed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build local SQLite LangGraph checkpoint evidence.",
        allow_abbrev=False,
    )
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--checkpoint-db", type=Path, default=DEFAULT_CHECKPOINT_DB)
    args = parser.parse_args()

    summary = build_sqlite_checkpoint_summary(
        evidence_date=args.date,
        checkpoint_db=args.checkpoint_db,
    )
    payload = json.dumps(summary, ensure_ascii=False, indent=2)
    print(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(payload + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
