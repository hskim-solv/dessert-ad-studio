from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import subprocess
import sys
from typing import Any


@dataclass(frozen=True)
class FastGateLane:
    name: str
    purpose: str
    commands: tuple[str, ...]
    parallel_safe: bool
    paid_api: bool = False
    external_services: bool = False
    notes: str = ""


LANES: dict[str, FastGateLane] = {
    "agentic-rag": FastGateLane(
        name="agentic-rag",
        purpose=(
            "LangGraph control-plane, SSE, SQLite checkpoint, replay, and graph trace fast gate."
        ),
        commands=(
            ".venv/bin/pytest tests/test_agentic_rag.py tests/test_agentic_rag_smoke_script.py "
            "tests/test_agentic_rag_stream_smoke_script.py "
            "tests/test_api.py::test_agentic_rag_run_stream_emits_redacted_worker_events "
            "tests/test_api.py::test_agentic_rag_run_replay_returns_redacted_sqlite_checkpoint_summary "
            "tests/test_api.py::test_agentic_rag_run_replay_returns_404_for_unknown_run "
            "tests/test_api.py::test_agentic_rag_run_stream_routes_paid_provider_to_approval -q",
            ".venv/bin/python scripts/agentic_rag_graph_smoke.py --output /tmp/agentic-rag-graph-summary.json",
            ".venv/bin/python scripts/agentic_rag_stream_smoke.py --output /tmp/agentic-rag-stream-summary.json",
            ".venv/bin/python scripts/agentic_rag_sqlite_checkpoint_smoke.py --output /tmp/agentic-rag-sqlite-checkpoint-summary.json --checkpoint-db /tmp/agentic-rag-checkpoints.sqlite",
            ".venv/bin/python scripts/agentic_rag_trace_smoke.py --output /tmp/agentic-rag-trace-summary.json",
        ),
        parallel_safe=True,
        notes="Uses /tmp outputs for generated summaries, traces, and SQLite checkpoints.",
    ),
    "docs": FastGateLane(
        name="docs",
        purpose="Documentation, ADR, and evidence formatting gate.",
        commands=(
            ".venv/bin/ruff check .",
            ".venv/bin/ruff format --check .",
            "git diff --check",
        ),
        parallel_safe=True,
    ),
    "offline-eval": FastGateLane(
        name="offline-eval",
        purpose="Offline retrieval, cost, visual, and postmortem evidence checks.",
        commands=(
            ".venv/bin/python scripts/eval_marketing_context.py --output /tmp/rag-baseline-results.json",
            ".venv/bin/python scripts/eval_pgvector_marketing_context.py --output /tmp/pgvector-baseline-results.json",
            ".venv/bin/python scripts/eval_visual_quality.py --output /tmp/visual-quality-summary.json",
            ".venv/bin/python scripts/cost_guard_smoke.py --model-id gpt-image-2 --image-total-tokens 627 --max-estimated-cost-usd 0.02 --output /tmp/cost-guard-summary.json",
            ".venv/bin/python scripts/analyze_provider_gate_failure.py --input docs/evidence/openai-image-edit-preservation-live-summary.json --output /tmp/provider-gate-postmortem-summary.json",
        ),
        parallel_safe=True,
        notes="Offline only; writes summaries to /tmp.",
    ),
    "compose": FastGateLane(
        name="compose",
        purpose="Docker Compose render gate without starting services.",
        commands=("docker compose config -q",),
        parallel_safe=True,
        external_services=False,
    ),
    "paid-provider": FastGateLane(
        name="paid-provider",
        purpose="Live OpenAI provider smoke; requires explicit human budget decision.",
        commands=(
            ".venv/bin/python scripts/openai_product_analysis_smoke.py --eval --eval-count 10 --output /tmp/product-analysis-openai-eval-results.json",
            ".venv/bin/python scripts/openai_image_edit_preservation_smoke.py --summary /tmp/openai-image-edit.json --output-dir /tmp/openai-image-edit",
        ),
        parallel_safe=False,
        paid_api=True,
        external_services=True,
        notes="Tripwire lane: do not execute without explicit paid API approval.",
    ),
}


def lane_payload(
    lane: FastGateLane, *, executed: bool, results: list[dict[str, Any]] | None = None
):
    return {
        "lane": lane.name,
        "purpose": lane.purpose,
        "commands": list(lane.commands),
        "parallel_safe": lane.parallel_safe,
        "paid_api": lane.paid_api,
        "external_services": lane.external_services,
        "notes": lane.notes,
        "executed": executed,
        "results": results or [],
    }


def list_payload() -> dict[str, Any]:
    return {
        "lanes": sorted(LANES),
        "parallel_safe_lanes": sorted(
            name for name, lane in LANES.items() if lane.parallel_safe and not lane.paid_api
        ),
        "tripwire_lanes": sorted(name for name, lane in LANES.items() if lane.paid_api),
    }


def run_lane(lane: FastGateLane) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for command in lane.commands:
        completed = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            check=False,
            text=True,
            timeout=180,
        )
        results.append(
            {
                "command": command,
                "returncode": completed.returncode,
                "stdout_tail": completed.stdout[-2000:],
                "stderr_tail": completed.stderr[-2000:],
            }
        )
        if completed.returncode != 0:
            break
    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run or list lane-specific fast gates for AI agent team workflows.",
        allow_abbrev=False,
    )
    parser.add_argument("--list", action="store_true", help="List available fast-gate lanes.")
    parser.add_argument("--lane", choices=sorted(LANES), help="Lane to inspect or run.")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing.")
    parser.add_argument(
        "--execute", action="store_true", help="Execute the selected lane commands."
    )
    args = parser.parse_args()

    if args.list:
        print(json.dumps(list_payload(), ensure_ascii=False, indent=2))
        return 0
    if not args.lane:
        parser.error("--lane is required unless --list is used")

    lane = LANES[args.lane]
    if args.execute:
        if lane.paid_api:
            print(json.dumps(lane_payload(lane, executed=False), ensure_ascii=False, indent=2))
            return 2
        results = run_lane(lane)
        print(
            json.dumps(
                lane_payload(lane, executed=True, results=results), ensure_ascii=False, indent=2
            )
        )
        return 0 if all(result["returncode"] == 0 for result in results) else 1

    print(json.dumps(lane_payload(lane, executed=False), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
