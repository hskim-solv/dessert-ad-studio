from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
from typing import Any


DEFAULT_REPORT_OUTPUT = Path("docs/evidence/agentic-rag-final-readiness.md")
DEFAULT_SUMMARY_OUTPUT = Path("docs/evidence/agentic-rag-final-readiness-summary.json")

SOURCE_ARTIFACTS = {
    "final_outcome": Path("docs/reference/dessert-ad-studio-final-outcome.md"),
    "readme": Path("README.md"),
    "evidence_map": Path("docs/evidence/README.md"),
    "architecture_diagram": Path("docs/evidence/assets/architecture.svg"),
    "graph": Path("docs/evidence/agentic-rag-graph-summary.json"),
    "stream": Path("docs/evidence/agentic-rag-stream-summary.json"),
    "websocket": Path("docs/evidence/agentic-rag-websocket-summary.json"),
    "checkpoint": Path("docs/evidence/agentic-rag-sqlite-checkpoint-summary.json"),
    "approval": Path("docs/evidence/agentic-rag-approval-summary.json"),
    "cross_process_resume": Path("docs/evidence/agentic-rag-cross-process-resume-summary.json"),
    "tools": Path("docs/evidence/agentic-rag-tools-summary.json"),
    "mcp": Path("docs/evidence/agentic-rag-mcp-server-summary.json"),
    "eval_report": Path("docs/evidence/agentic-rag-eval-report-summary.json"),
    "trace": Path("docs/evidence/agentic-rag-trace-summary.json"),
    "run_metrics": Path("docs/evidence/agentic-rag-run-metrics-summary.json"),
    "retention": Path("docs/evidence/agentic-rag-retention-policy-summary.json"),
    "rag_baseline": Path("docs/evidence/rag-baseline-results.json"),
    "chunking": Path("docs/evidence/rag-chunking-comparison-results.json"),
    "pgvector": Path("docs/evidence/pgvector-baseline-results.json"),
    "k8s": Path("docs/evidence/k8s-live-smoke-summary.json"),
    "demo_storyboard": Path("docs/evidence/demo-video-storyboard-summary.json"),
    "decision_register": Path("docs/evidence/agentic-rag-decision-register-summary.json"),
    "provider_visual_review": Path("docs/evidence/provider-visual-review-summary.json"),
    "provider_postmortem": Path("docs/evidence/provider-gate-postmortem-summary.json"),
}


def build_agentic_rag_final_readiness_summary(*, evidence_date: str) -> dict[str, Any]:
    artifacts = _load_artifacts(SOURCE_ARTIFACTS)
    source_artifacts = [str(path) for path in SOURCE_ARTIFACTS.values()]
    missing_artifacts = [name for name, payload in artifacts.items() if payload is None]

    decision_register = _required(artifacts, "decision_register")
    provider_visual = _required(artifacts, "provider_visual_review")
    provider_postmortem = _required(artifacts, "provider_postmortem")

    capabilities = [
        _capability(
            "backend_async_streaming",
            "FastAPI async SSE/WebSocket run streaming and replay",
            "first_gate_passed",
            [
                _json_passed(artifacts, "stream", "agentic_rag_stream_smoke"),
                _json_passed(artifacts, "websocket", "agentic_rag_websocket_smoke"),
                _field_is(artifacts, "stream", "checkpointing_enabled", True),
                _field_is(artifacts, "websocket", "stream_protocol", "websocket"),
            ],
            [
                "docs/evidence/agentic-rag-streaming.md",
                str(SOURCE_ARTIFACTS["stream"]),
                str(SOURCE_ARTIFACTS["websocket"]),
            ],
        ),
        _capability(
            "langgraph_orchestration",
            "LangGraph typed graph, conditional routing, retry/reflection, checkpointing, HITL",
            "first_gate_passed",
            [
                _json_passed(artifacts, "graph", "agentic_rag_graph_smoke"),
                _json_passed(artifacts, "checkpoint", "agentic_rag_sqlite_checkpoint_smoke"),
                _json_passed(artifacts, "approval", "agentic_rag_approval_smoke"),
                _json_passed(
                    artifacts,
                    "cross_process_resume",
                    "agentic_rag_cross_process_resume_smoke",
                ),
            ],
            [
                "docs/evidence/agentic-rag-graph.md",
                "docs/evidence/agentic-rag-sqlite-checkpoint.md",
                "docs/evidence/agentic-rag-approval.md",
                "docs/evidence/agentic-rag-cross-process-resume.md",
            ],
        ),
        _capability(
            "rag_retrieval",
            "Document retrieval, chunking comparison, embeddings, pgvector hybrid retrieval, citations, fallback",
            "first_gate_passed",
            [
                _field_is(artifacts, "rag_baseline", "passed", True),
                _json_passed(artifacts, "chunking", "rag_chunking_comparison"),
                _field_is(artifacts, "pgvector", "passed", True),
                _nested_gte(artifacts, "eval_report", ["retrieval", "pgvector_precision"], 1.0),
            ],
            [
                "docs/evidence/rag-baseline.md",
                "docs/evidence/rag-chunking-comparison.md",
                "docs/evidence/pgvector-retrieval.md",
                str(SOURCE_ARTIFACTS["eval_report"]),
            ],
        ),
        _capability(
            "tool_suite_and_mcp",
            "Document retrieval, web search, SQL, internal API, generation workflow, and FastMCP tool server",
            "first_gate_passed",
            [
                _json_passed(artifacts, "tools", "agentic_rag_tools_smoke"),
                _json_passed(artifacts, "mcp", "agentic_rag_mcp_server_smoke"),
                _field_is(artifacts, "tools", "raw_inputs_committed", False),
                _field_is(artifacts, "mcp", "raw_inputs_committed", False),
            ],
            [
                "docs/evidence/agentic-rag-tools.md",
                str(SOURCE_ARTIFACTS["tools"]),
                str(SOURCE_ARTIFACTS["mcp"]),
            ],
        ),
        _capability(
            "evaluation_and_ci",
            "Ragas-compatible golden eval, promptfoo regression, guardrail gate, and reviewer eval report",
            "first_gate_passed_with_live_ragas_pending",
            [
                _json_passed(artifacts, "eval_report", "agentic_rag_eval_report"),
                _field_is(
                    artifacts,
                    "eval_report",
                    "scope",
                    "offline_reviewer_eval_report_no_paid_api_call",
                ),
                _nested_gte(artifacts, "eval_report", ["golden_eval", "case_count"], 13),
                _nested_is(artifacts, "eval_report", ["promptfoo", "passed"], True),
                _nested_is(
                    artifacts,
                    "eval_report",
                    ["limits", "ragas_live_gate"],
                    "pending_paid_api_approval",
                ),
            ],
            [
                "docs/evidence/agentic-rag-eval-guardrail.md",
                "docs/evidence/agentic-rag-eval-report.md",
                str(SOURCE_ARTIFACTS["eval_report"]),
            ],
        ),
        _capability(
            "observability",
            "OpenInference/Phoenix-compatible traces, latency, token/cost, tool success/failure, failed-run analysis",
            "first_gate_passed",
            [
                _json_passed(artifacts, "trace", "agentic_rag_trace_smoke"),
                _json_passed(artifacts, "run_metrics", "agentic_rag_run_metrics_smoke"),
                _field_is(artifacts, "trace", "raw_inputs_committed", False),
                _field_is(artifacts, "run_metrics", "raw_inputs_committed", False),
            ],
            [
                "docs/evidence/agentic-rag-trace.md",
                "docs/evidence/agentic-rag-run-metrics.md",
                "docs/evidence/agentops-phoenix.md",
            ],
        ),
        _capability(
            "guardrails_privacy",
            "Structured validation, tool allowlist, prompt injection, tool budget, redaction, fallback, retention boundary",
            "first_gate_passed_with_production_storage_pending",
            [
                _nested_is(
                    artifacts,
                    "eval_report",
                    ["guardrails", "prompt_injection_blocked"],
                    True,
                ),
                _nested_is(artifacts, "eval_report", ["guardrails", "tool_budget_passed"], True),
                _json_passed(artifacts, "retention", "agentic_rag_retention_policy_smoke"),
                _field_is(artifacts, "retention", "raw_inputs_committed", False),
            ],
            [
                "docs/evidence/agentic-rag-eval-guardrail.md",
                "docs/evidence/agentic-rag-retention-policy.md",
                str(SOURCE_ARTIFACTS["decision_register"]),
            ],
        ),
        _capability(
            "deployment_packaging",
            "Docker/GitHub Actions/Kubernetes evidence, architecture diagram, storyboard, eval report",
            "first_gate_passed_with_cloud_demo_file_pending",
            [
                _json_passed(artifacts, "k8s", "k8s_live_smoke"),
                _path_exists(artifacts, "architecture_diagram"),
                _json_passed(artifacts, "demo_storyboard", "demo_video_storyboard"),
                _field_is(artifacts, "demo_storyboard", "actual_video_file_committed", False),
                _json_passed(artifacts, "eval_report", "agentic_rag_eval_report"),
            ],
            [
                "docs/evidence/k8s-deployment.md",
                "docs/evidence/assets/architecture.svg",
                "docs/evidence/demo-video-storyboard.md",
                "docs/evidence/agentic-rag-eval-report.md",
            ],
        ),
        _capability(
            "provider_quality_claim_boundary",
            "Provider-quality image editing remains unproven until latency strategy and later paid gate pass",
            "not_claimed",
            [
                _field_is(artifacts, "provider_visual_review", "provider_quality_claimed", False),
                _field_is(artifacts, "provider_visual_review", "provider_quality_unproven", True),
                _field_is(
                    artifacts,
                    "provider_postmortem",
                    "provider_gate_postmortem",
                    "failed_gate_analyzed",
                ),
                _list_contains(
                    artifacts, "provider_postmortem", "root_causes", "latency_threshold_exceeded"
                ),
            ],
            [
                "docs/evidence/provider-visual-review.md",
                "docs/evidence/provider-gate-postmortem.md",
                "docs/evidence/openai-image-edit-preservation.md",
            ],
        ),
    ]

    pending_decisions = decision_register["decisions"]
    passed = (
        not missing_artifacts
        and all(capability["passed"] for capability in capabilities)
        and decision_register["decisions_requiring_user_approval"]
        == decision_register["decision_count"]
        and decision_register["production_claim_added"] is False
        and provider_visual["provider_quality_claimed"] is False
        and provider_postmortem["root_causes"] == ["latency_threshold_exceeded"]
    )

    return {
        "agentic_rag_final_readiness": "passed" if passed else "failed",
        "scope": "portfolio_boundary_audit_no_paid_api_call",
        "evidence_date": evidence_date,
        "source_artifacts": source_artifacts,
        "missing_artifacts": missing_artifacts,
        "capabilities": capabilities,
        "capability_counts": {
            "total": len(capabilities),
            "passed": sum(1 for capability in capabilities if capability["passed"]),
            "first_gate_statuses": sorted(
                {
                    capability["status"]
                    for capability in capabilities
                    if capability["status"].startswith("first_gate")
                }
            ),
            "not_claimed": sum(
                1 for capability in capabilities if capability["status"] == "not_claimed"
            ),
        },
        "pending_decision_register": {
            "decision_count": decision_register["decision_count"],
            "decisions_requiring_user_approval": decision_register[
                "decisions_requiring_user_approval"
            ],
            "production_claim_added": decision_register["production_claim_added"],
            "decision_ids": [decision["id"] for decision in pending_decisions],
        },
        "provider_quality_boundary": {
            "provider_quality_claimed": provider_visual["provider_quality_claimed"],
            "provider_quality_unproven": provider_visual["provider_quality_unproven"],
            "latest_paid_canary": provider_visual["latest_paid_canary"],
            "root_causes": provider_postmortem["root_causes"],
        },
        "completion_claim": {
            "production_complete": False,
            "reason": (
                "Local first gates and reviewer packaging are consolidated, but "
                "live/API-key, credentialed DB, production MCP auth, external trace, "
                "cloud/demo, and image latency decisions remain user-gated."
            ),
        },
        "privacy_boundary": {
            "paid_api_call_count": 0,
            "raw_inputs_committed": False,
        },
    }


def render_agentic_rag_final_readiness(summary: dict[str, Any]) -> str:
    capability_rows = "\n".join(
        "| `{id}` | `{status}` | `{passed}` | {evidence} |".format(
            id=capability["id"],
            status=capability["status"],
            passed=str(capability["passed"]).lower(),
            evidence=", ".join(f"`{path}`" for path in capability["evidence"][:3]),
        )
        for capability in summary["capabilities"]
    )
    decision_ids = ", ".join(summary["pending_decision_register"]["decision_ids"])
    source_rows = "\n".join(f"- `{path}`" for path in summary["source_artifacts"])
    provider = summary["provider_quality_boundary"]
    return f"""# Agentic RAG Final Readiness Audit

Date: {summary["evidence_date"]}

This audit maps the final portfolio target to current evidence. It does not run
paid APIs, live web search, credentialed databases, external trace backends, or
cloud deployment.

## Result

- `agentic_rag_final_readiness`: `{summary["agentic_rag_final_readiness"]}`
- `scope`: `{summary["scope"]}`
- Capabilities passed: `{summary["capability_counts"]["passed"]}` /
  `{summary["capability_counts"]["total"]}`
- Missing artifacts: `{summary["missing_artifacts"]}`
- Production complete: `{summary["completion_claim"]["production_complete"]}`
- Reason: {summary["completion_claim"]["reason"]}

## Capability Matrix

| Capability | Status | Passed | Evidence |
|---|---|---|---|
{capability_rows}

## Pending Decisions

- Pending user decisions:
  `{summary["pending_decision_register"]["decision_count"]}`
- Decisions requiring approval:
  `{summary["pending_decision_register"]["decisions_requiring_user_approval"]}`
- Production claim added:
  `{summary["pending_decision_register"]["production_claim_added"]}`
- Decision IDs: `{decision_ids}`

## Provider-Quality Boundary

- Provider-quality claimed:
  `{provider["provider_quality_claimed"]}`
- Provider-quality unproven:
  `{provider["provider_quality_unproven"]}`
- Latest paid canary elapsed:
  `{provider["latest_paid_canary"]["elapsed_ms"]} ms`
- Latest paid canary estimated cost:
  `${provider["latest_paid_canary"]["estimated_cost_usd"]}`
- Root causes: `{", ".join(provider["root_causes"])}`

## Source Artifacts

{source_rows}

## Reproduce

```bash
.venv/bin/python scripts/build_agentic_rag_final_readiness.py \\
  --date {summary["evidence_date"]} \\
  --report-output docs/evidence/agentic-rag-final-readiness.md \\
  --summary-output docs/evidence/agentic-rag-final-readiness-summary.json
```
"""


def _load_artifacts(paths: dict[str, Path]) -> dict[str, Any | None]:
    artifacts: dict[str, Any | None] = {}
    for name, path in paths.items():
        if not path.exists():
            artifacts[name] = None
        elif path.suffix == ".json":
            artifacts[name] = json.loads(path.read_text(encoding="utf-8"))
        else:
            artifacts[name] = {"path_exists": True}
    return artifacts


def _required(artifacts: dict[str, Any | None], name: str) -> dict[str, Any]:
    payload = artifacts[name]
    if not isinstance(payload, dict):
        raise FileNotFoundError(f"Missing required artifact: {SOURCE_ARTIFACTS[name]}")
    return payload


def _capability(
    capability_id: str,
    description: str,
    status: str,
    checks: list[bool],
    evidence: list[str],
) -> dict[str, Any]:
    return {
        "id": capability_id,
        "description": description,
        "status": status,
        "passed": all(checks),
        "checks_passed": sum(1 for check in checks if check),
        "checks_total": len(checks),
        "evidence": evidence,
    }


def _path_exists(artifacts: dict[str, Any | None], name: str) -> bool:
    payload = artifacts.get(name)
    return isinstance(payload, dict) and payload.get("path_exists") is True


def _json_passed(artifacts: dict[str, Any | None], name: str, key: str) -> bool:
    payload = artifacts.get(name)
    return isinstance(payload, dict) and payload.get(key) == "passed"


def _field_is(artifacts: dict[str, Any | None], name: str, key: str, expected: Any) -> bool:
    payload = artifacts.get(name)
    return isinstance(payload, dict) and payload.get(key) == expected


def _nested_is(
    artifacts: dict[str, Any | None],
    name: str,
    path: list[str],
    expected: Any,
) -> bool:
    value = _nested_value(artifacts, name, path)
    return value == expected


def _nested_gte(
    artifacts: dict[str, Any | None],
    name: str,
    path: list[str],
    minimum: float,
) -> bool:
    value = _nested_value(artifacts, name, path)
    return isinstance(value, int | float) and value >= minimum


def _nested_value(artifacts: dict[str, Any | None], name: str, path: list[str]) -> Any:
    value: Any = artifacts.get(name)
    for part in path:
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _list_contains(
    artifacts: dict[str, Any | None],
    name: str,
    key: str,
    expected: Any,
) -> bool:
    payload = artifacts.get(name)
    if not isinstance(payload, dict):
        return False
    value = payload.get(key)
    return isinstance(value, list) and expected in value


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a final Agentic RAG readiness audit from committed evidence."
    )
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT_OUTPUT)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY_OUTPUT)
    args = parser.parse_args()

    summary = build_agentic_rag_final_readiness_summary(evidence_date=args.date)
    summary_payload = json.dumps(summary, ensure_ascii=False, indent=2)
    report_payload = render_agentic_rag_final_readiness(summary)

    args.summary_output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    args.summary_output.write_text(summary_payload + "\n", encoding="utf-8")
    args.report_output.write_text(report_payload, encoding="utf-8")
    print(summary_payload)
    return 0 if summary["agentic_rag_final_readiness"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
