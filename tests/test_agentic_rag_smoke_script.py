from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_agentic_rag_graph_smoke_writes_redacted_summary(tmp_path: Path) -> None:
    output_path = tmp_path / "agentic-rag-graph-summary.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/agentic_rag_graph_smoke.py",
            "--output",
            str(output_path),
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
        timeout=60,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    summary = json.loads(output_path.read_text(encoding="utf-8"))

    assert summary["agentic_rag_graph_smoke"] == "passed"
    assert summary["scope"] == "offline_langgraph_control_plane_no_paid_api_call"
    assert summary["approval_route"]["status"] == "needs_approval"
    assert summary["approval_route"]["next_action"] == "wait_for_human_approval"
    assert summary["approval_route"]["node_trace"] == [
        "plan_campaign",
        "run_tool_suite",
        "retrieve_context",
        "build_citations",
        "guardrail_check",
        "human_approval",
    ]
    assert summary["approval_route"]["checkpoint_count"] >= 1
    assert summary["approval_route"]["citation_count"] >= 1
    assert summary["approval_route"]["approval_required"] is True
    assert summary["worker_route"]["status"] == "completed"
    assert summary["worker_route"]["next_action"] == "return_cited_ad_package"
    assert summary["worker_route"]["worker_status"] == "succeeded"
    assert summary["worker_route"]["copy_option_count"] == 3
    assert summary["worker_route"]["cited_ad_package_ready"] is True
    assert summary["worker_route"]["cited_ad_package_source_doc_count"] >= 1
    assert summary["worker_route"]["raw_assets_committed"] is False
    assert summary["worker_route"]["node_trace"] == [
        "plan_campaign",
        "run_tool_suite",
        "retrieve_context",
        "build_citations",
        "guardrail_check",
        "execute_worker",
        "finalize",
    ]

    serialized = json.dumps(summary, ensure_ascii=False)
    for raw_value in [
        "비공개 말차 푸딩",
        "VIP 고객에게만 보일 문구",
        "비공개 딸기 크림 크루아상",
        "VIP 촬영본",
        "secret-reference.png",
        "c2VjcmV0LWltYWdlLWJ5dGVz",
    ]:
        assert raw_value not in serialized


def test_agentic_rag_sqlite_checkpoint_smoke_writes_redacted_summary(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "agentic-rag-sqlite-checkpoint-summary.json"
    checkpoint_path = tmp_path / "agentic-rag-checkpoints.sqlite"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/agentic_rag_sqlite_checkpoint_smoke.py",
            "--output",
            str(output_path),
            "--checkpoint-db",
            str(checkpoint_path),
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
        timeout=60,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    summary = json.loads(output_path.read_text(encoding="utf-8"))

    assert summary["agentic_rag_sqlite_checkpoint_smoke"] == "passed"
    assert summary["scope"] == "local_sqlite_langgraph_checkpointer_no_paid_api_call"
    assert summary["checkpoint_backend"] == "sqlite"
    assert summary["checkpoint_path_committed"] is False
    assert summary["checkpoint_file_created"] is True
    assert summary["checkpoint_count"] >= 1
    assert summary["reopened_checkpoint_count"] == summary["checkpoint_count"]
    assert summary["raw_inputs_found_in_checkpoint"] is False
    assert summary["final_status"] == "completed"
    assert summary["next_action"] == "return_cited_ad_package"
    assert summary["cited_ad_package_ready"] is True
    assert summary["cited_ad_package_source_doc_count"] >= 1
    assert summary["raw_assets_committed"] is False

    serialized = json.dumps(summary, ensure_ascii=False)
    checkpoint_bytes = checkpoint_path.read_bytes()
    for raw_value in [
        "비공개 말차 푸딩",
        "VIP 고객에게만 보일 문구",
        "비공개 할인 강조",
        "secret-reference.png",
        "c2VjcmV0LWltYWdlLWJ5dGVz",
    ]:
        assert raw_value not in serialized
        assert raw_value.encode("utf-8") not in checkpoint_bytes


def test_agentic_rag_trace_smoke_writes_redacted_summary(tmp_path: Path) -> None:
    output_path = tmp_path / "agentic-rag-trace-summary.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/agentic_rag_trace_smoke.py",
            "--output",
            str(output_path),
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
        timeout=60,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    summary = json.loads(output_path.read_text(encoding="utf-8"))

    assert summary["agentic_rag_trace_smoke"] == "passed"
    assert summary["scope"] == "local_in_memory_openinference_trace_no_paid_api_call"
    assert summary["span_names"] == [
        "agentic_rag.plan_campaign",
        "agentic_rag.run_tool_suite",
        "agentic_rag.retrieve_context",
        "agentic_rag.build_citations",
        "agentic_rag.guardrail_check",
        "agentic_rag.execute_worker",
        "agentic_rag.finalize",
    ]
    assert summary["span_kinds"] == [
        "AGENT",
        "TOOL",
        "RETRIEVER",
        "CHAIN",
        "GUARDRAIL",
        "TOOL",
        "CHAIN",
    ]
    assert summary["raw_inputs_committed"] is False

    serialized = json.dumps(summary, ensure_ascii=False)
    assert "비공개 말차 푸딩" not in serialized
    assert "VIP 고객" not in serialized


def test_agentic_rag_run_metrics_smoke_writes_redacted_summary(tmp_path: Path) -> None:
    output_path = tmp_path / "agentic-rag-run-metrics-summary.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/agentic_rag_run_metrics_smoke.py",
            "--output",
            str(output_path),
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
        timeout=60,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    summary = json.loads(output_path.read_text(encoding="utf-8"))

    assert summary["agentic_rag_run_metrics_smoke"] == "passed"
    assert summary["scope"] == "local_agentic_rag_metrics_no_paid_api_call"
    assert summary["paid_api_call_count"] == 0
    assert summary["token_usage"]["estimated_total_tokens"] == 0
    assert summary["cost"]["estimated_total_usd"] == 0.0
    assert summary["latency"]["span_count"] >= 7
    assert summary["latency"]["total_elapsed_ms"] >= 0.0
    assert summary["tool_calls"]["planned_count"] == 7
    assert summary["tool_calls"]["result_count"] == 3
    assert summary["tool_calls"]["success_count"] == 3
    assert summary["tool_calls"]["failure_count"] == 0
    assert summary["failed_run_analysis"]["status"] == "failed"
    assert summary["failed_run_analysis"]["next_action"] == "inspect_failed_run"
    assert summary["failed_run_analysis"]["worker_error_types"] == ["RuntimeError"]
    assert summary["failed_run_analysis"]["retry_attempts"] == 1
    assert summary["failed_run_analysis"]["graceful_fallback_ready"] is True
    assert summary["failed_run_analysis"]["fallback_reason"] == "worker_failed_after_retry_budget"
    assert summary["failed_run_analysis"]["fallback_next_action"] == "inspect_failed_run"
    assert summary["failed_run_analysis"]["fallback_retry_attempts"] == 1
    assert summary["failed_run_analysis"]["fallback_retry_budget"] == 1
    assert summary["failed_run_analysis"]["fallback_last_error_type"] == "RuntimeError"
    assert summary["failed_run_analysis"]["raw_error_committed"] is False
    assert summary["failed_run_analysis"]["raw_inputs_committed"] is False
    assert summary["raw_inputs_committed"] is False

    serialized = json.dumps(summary, ensure_ascii=False)
    for raw_value in [
        "비공개 말차 푸딩",
        "VIP 고객",
        "raw private customer text",
    ]:
        assert raw_value not in serialized


def test_agentic_rag_tools_smoke_writes_redacted_summary(tmp_path: Path) -> None:
    output_path = tmp_path / "agentic-rag-tools-summary.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/agentic_rag_tools_smoke.py",
            "--output",
            str(output_path),
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
        timeout=60,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    summary = json.loads(output_path.read_text(encoding="utf-8"))

    assert summary["agentic_rag_tools_smoke"] == "passed"
    assert summary["scope"] == "local_tool_suite_no_network_no_paid_api_call"
    assert summary["planned_tools"] == [
        "document_retrieval",
        "web_search",
        "sql_query",
        "internal_api",
        "citation_builder",
        "guardrail_check",
        "generation_workflow",
    ]
    assert summary["max_tool_calls"] == 7
    assert summary["tool_result_keys"] == ["internal_api", "sql_query", "web_search"]
    assert summary["web_search"]["mode"] == "local_curated_snapshot"
    assert summary["sql_query"]["mode"] == "sqlite_allowlisted_query"
    assert summary["internal_api"]["mode"] == "in_process_contract"
    assert summary["document_retrieval"]["retriever_backend"] == "keyword"
    assert summary["mcp_server_scaffold"] == "mcp_servers/dessert_ad_studio_server.py"
    assert summary["raw_inputs_committed"] is False

    serialized = json.dumps(summary, ensure_ascii=False)
    assert "비공개 말차 푸딩" not in serialized
    assert "VIP 고객" not in serialized
