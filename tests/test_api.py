import base64
import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from api.main import app

client = TestClient(app)


def base_payload() -> dict:
    return {
        "campaign_purpose": "new_menu",
        "product_name": "말차 푸딩",
        "tone": "clean",
        "template_hint": "minimal_premium",
        "price_text": "5,500원",
        "user_constraints": "깔끔한 프리미엄 느낌",
    }


def tiny_png_b64() -> str:
    buffer = io.BytesIO()
    Image.new("RGB", (16, 16), color=(120, 200, 160)).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _parse_sse_events(body: str) -> list[dict]:
    events: list[dict] = []
    for raw_event in body.strip().split("\n\n"):
        event_name = ""
        data = ""
        for line in raw_event.splitlines():
            if line.startswith("event: "):
                event_name = line.removeprefix("event: ")
            elif line.startswith("data: "):
                data = line.removeprefix("data: ")
        events.append({"event": event_name, "data": json.loads(data)})
    return events


def _receive_agentic_rag_websocket_messages(websocket) -> list[dict]:
    messages: list[dict] = []
    while True:
        message = websocket.receive_json()
        messages.append(message)
        if message["event"] == "run_completed":
            return messages


def _receive_agentic_rag_websocket_messages_until(websocket, event_name: str) -> list[dict]:
    messages: list[dict] = []
    while True:
        message = websocket.receive_json()
        messages.append(message)
        if message["event"] == event_name:
            return messages


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_livez() -> None:
    response = client.get("/livez")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_readyz(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))

    response = client.get("/readyz")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["copy_backend"] == "mock"
    assert body["image_backend"] == "mock"
    assert body["product_analysis_backend"] == "mock"
    assert body["template_scorer"] == "local-template-scorer"


def test_readyz_rejects_bad_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPY_BACKEND", "missing")

    response = client.get("/readyz")

    assert response.status_code == 503
    assert "unknown copy backend: missing" in response.json()["detail"]


def test_readyz_rejects_openai_backend_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    import api.main as api_main

    api_main._copy_backend_for.cache_clear()
    monkeypatch.setenv("COPY_BACKEND", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    response = client.get("/readyz")

    assert response.status_code == 503
    assert "OPENAI_API_KEY" in response.json()["detail"]


def test_readyz_maps_pgvector_connection_failure_to_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.main as api_main

    api_main._marketing_context_retriever_for.cache_clear()
    monkeypatch.setenv("MARKETING_CONTEXT_BACKEND", "pgvector_hybrid")
    monkeypatch.setenv(
        "PGVECTOR_DSN",
        "postgresql://dessert:bad-password@127.0.0.1:1/missing",
    )

    response = client.get("/readyz")

    assert response.status_code == 503
    assert "pgvector_hybrid retriever is not ready" in response.json()["detail"]


def test_readyz_checks_required_triton(monkeypatch: pytest.MonkeyPatch) -> None:
    import api.main as api_main

    monkeypatch.setenv("REQUIRE_TRITON", "1")
    monkeypatch.setattr(api_main, "_is_triton_ready", lambda url: False)

    response = client.get("/readyz")

    assert response.status_code == 503
    assert "triton template_scorer is not ready" in response.json()["detail"]


def test_metrics_exposes_prometheus_text() -> None:
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert 'dessert_ad_studio_info{service="api"} 1' in response.text
    assert "dessert_ad_studio_http_requests_total" in response.text


def test_metrics_uses_route_template_for_a2a_task_paths(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    request = {
        "message": {
            "role": "ROLE_USER",
            "messageId": "msg-metrics-task",
            "parts": [{"data": base_payload()}],
        }
    }

    task_response = client.post(
        "/message:send",
        json=request,
        headers={"content-type": "application/a2a+json"},
    )
    assert task_response.status_code == 200
    task_id = task_response.json()["task"]["id"]

    get_response = client.get(f"/tasks/{task_id}")
    assert get_response.status_code == 200

    metrics_response = client.get("/metrics")

    assert metrics_response.status_code == 200
    assert 'path="/tasks/{task_id}"' in metrics_response.text
    assert f'path="/tasks/{task_id}"' not in metrics_response.text


def test_metrics_uses_sentinel_for_unmatched_paths() -> None:
    response_a = client.get("/missing-a-review-1")
    response_b = client.get("/missing-b-review-2")

    assert response_a.status_code == 404
    assert response_b.status_code == 404

    metrics_response = client.get("/metrics")

    assert metrics_response.status_code == 200
    assert 'path="__unmatched__"' in metrics_response.text
    assert "/missing-a-review-1" not in metrics_response.text
    assert "/missing-b-review-2" not in metrics_response.text


def test_generate_uses_template_ranking_and_returns_copy() -> None:
    response = client.post("/generate", json=base_payload())

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["copy_options"]) == 3
    assert payload["selected_template"]["scorer"] in {
        "local-template-scorer",
        "triton-template-scorer",
    }
    assert payload["copy_backend"] == "mock"
    assert payload["image_backend"] == "mock"
    assert payload["used_reference"] is False
    assert payload["image_path"].endswith(".png")
    assert payload["product_analysis"]["analyzer_backend"] == "mock"
    assert payload["marketing_context"]["retriever_backend"] == "keyword"
    assert payload["marketing_context"]["retrieved_docs_count"] >= 1
    assert payload["elapsed_ms"] >= 0


def test_generate_accepts_revision_request(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    payload = {
        **base_payload(),
        "revision_request": "더 프리미엄하고 문구를 짧게 수정",
    }

    response = client.post("/generate", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert "수정 요청: 더 프리미엄하고 문구를 짧게 수정" in body["prompt_summary"]
    assert "더 프리미엄" in body["copy_options"][0]["body"]


def test_generate_can_use_pgvector_hybrid_marketing_context_backend(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import api.main as api_main

    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("MARKETING_CONTEXT_BACKEND", "pgvector_hybrid")
    monkeypatch.delenv("PGVECTOR_DSN", raising=False)
    api_main._marketing_context_retriever_for.cache_clear()

    response = client.post("/generate", json=base_payload())

    assert response.status_code == 200
    context = response.json()["marketing_context"]
    assert context["retriever_backend"] == "pgvector_hybrid"
    assert context["guide_categories"] == ["premium", "cafe", "prohibited_claims"]


def test_generate_maps_pgvector_connection_failure_to_503(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import api.main as api_main

    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("MARKETING_CONTEXT_BACKEND", "pgvector_hybrid")
    monkeypatch.setenv(
        "PGVECTOR_DSN",
        "postgresql://dessert:bad-password@127.0.0.1:1/missing",
    )
    api_main._marketing_context_retriever_for.cache_clear()

    response = client.post("/generate", json=base_payload())

    assert response.status_code == 503
    assert "pgvector_hybrid retriever is not ready" in response.json()["detail"]


def test_agentic_rag_run_stream_emits_redacted_worker_events(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("GENERATION_LOG_PATH", str(tmp_path / "generations.jsonl"))
    payload = {
        **base_payload(),
        "product_name": "비공개 말차 푸딩",
        "user_constraints": "VIP 고객에게만 보일 문구",
    }

    with client.stream("POST", "/agentic-rag/runs/stream", json=payload) as response:
        body = response.read().decode("utf-8")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse_events(body)
    assert [event["event"] for event in events] == [
        "run_started",
        "node_completed",
        "node_completed",
        "node_completed",
        "node_completed",
        "node_completed",
        "node_completed",
        "node_completed",
        "run_completed",
    ]
    assert [
        event["data"].get("node") for event in events if event["event"] == "node_completed"
    ] == [
        "plan_campaign",
        "run_tool_suite",
        "retrieve_context",
        "build_citations",
        "guardrail_check",
        "execute_worker",
        "finalize",
    ]
    assert events[-1]["data"] == {
        "status": "completed",
        "next_action": "return_cited_ad_package",
        "raw_inputs_committed": False,
    }
    worker_event = next(event for event in events if event["data"].get("node") == "execute_worker")
    assert worker_event["data"]["worker_status"] == "succeeded"
    assert worker_event["data"]["copy_option_count"] == 3
    assert worker_event["data"]["copy_backend"] == "mock"
    assert worker_event["data"]["image_backend"] == "mock"

    for raw_value in ["비공개 말차 푸딩", "VIP 고객에게만 보일 문구"]:
        assert raw_value not in body


def test_agentic_rag_stream_update_exposes_redacted_graceful_fallback() -> None:
    import api.main as api_main

    payload = api_main._agentic_rag_stream_update(
        "finalize",
        {
            "status": "failed",
            "next_action": "inspect_failed_run",
            "graceful_fallback": {
                "status": "ready",
                "reason": "worker_failed_after_retry_budget",
                "next_action": "inspect_failed_run",
                "retry_attempts": 1,
                "retry_budget": 1,
                "last_error_type": "RuntimeError",
                "raw_error_committed": False,
                "raw_inputs_committed": False,
            },
        },
    )

    assert payload == {
        "node": "finalize",
        "status": "failed",
        "next_action": "inspect_failed_run",
        "graceful_fallback_ready": True,
        "fallback_reason": "worker_failed_after_retry_budget",
        "fallback_next_action": "inspect_failed_run",
        "fallback_retry_attempts": 1,
        "fallback_retry_budget": 1,
        "fallback_last_error_type": "RuntimeError",
        "raw_error_committed": False,
        "raw_inputs_committed": False,
    }


def test_agentic_rag_run_replay_returns_redacted_sqlite_checkpoint_summary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("GENERATION_LOG_PATH", str(tmp_path / "generations.jsonl"))
    monkeypatch.setenv(
        "AGENTIC_RAG_CHECKPOINT_DB",
        str(tmp_path / "agentic-rag-checkpoints.sqlite"),
    )
    payload = {
        **base_payload(),
        "product_name": "비공개 말차 푸딩",
        "user_constraints": "VIP 고객에게만 보일 문구",
    }

    with client.stream("POST", "/agentic-rag/runs/stream", json=payload) as response:
        body = response.read().decode("utf-8")

    assert response.status_code == 200
    events = _parse_sse_events(body)
    run_id = events[0]["data"]["run_id"]
    assert run_id.startswith("agr-")
    assert events[0]["data"]["checkpointing_enabled"] is True

    replay_response = client.get(f"/agentic-rag/runs/{run_id}/replay")

    assert replay_response.status_code == 200
    replay = replay_response.json()
    assert replay["run_id"] == run_id
    assert replay["checkpoint_backend"] == "sqlite"
    assert replay["checkpoint_count"] >= 1
    assert replay["status"] == "completed"
    assert replay["next_action"] == "return_cited_ad_package"
    assert replay["node_trace"] == [
        "plan_campaign",
        "run_tool_suite",
        "retrieve_context",
        "build_citations",
        "guardrail_check",
        "execute_worker",
        "finalize",
    ]
    assert replay["worker_status"] == "succeeded"
    assert replay["copy_option_count"] == 3
    assert replay["cited_ad_package_ready"] is True
    assert replay["cited_ad_package_source_doc_count"] >= 1
    assert replay["raw_inputs_committed"] is False

    serialized = json.dumps(replay, ensure_ascii=False)
    for raw_value in ["비공개 말차 푸딩", "VIP 고객에게만 보일 문구"]:
        assert raw_value not in body
        assert raw_value not in serialized


def test_agentic_rag_run_replay_returns_404_for_unknown_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(
        "AGENTIC_RAG_CHECKPOINT_DB",
        str(tmp_path / "agentic-rag-checkpoints.sqlite"),
    )

    response = client.get("/agentic-rag/runs/agr-missing/replay")

    assert response.status_code == 404
    assert response.json()["detail"] == "Agentic RAG run replay not found."


def test_agentic_rag_run_approval_records_redacted_reviewer_decision(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import api.main as api_main

    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("GENERATION_LOG_PATH", str(tmp_path / "generations.jsonl"))
    monkeypatch.setenv(
        "AGENTIC_RAG_CHECKPOINT_DB",
        str(tmp_path / "agentic-rag-checkpoints.sqlite"),
    )
    monkeypatch.setattr(api_main, "_agentic_rag_requires_paid_provider", lambda deps: True)
    payload = {
        **base_payload(),
        "product_name": "비공개 말차 푸딩",
        "user_constraints": "VIP 고객에게만 보일 문구",
    }

    with client.stream("POST", "/agentic-rag/runs/stream", json=payload) as response:
        body = response.read().decode("utf-8")

    assert response.status_code == 200
    events = _parse_sse_events(body)
    run_id = events[0]["data"]["run_id"]

    approval_response = client.post(
        f"/agentic-rag/runs/{run_id}/approval",
        json={
            "decision": "approved",
            "reviewer_id": "reviewer@example.com",
            "comment": "VIP 고객 원문이 담긴 비공개 승인 메모",
        },
    )

    assert approval_response.status_code == 200
    approval = approval_response.json()
    assert approval["run_id"] == run_id
    assert approval["status"] == "approved"
    assert approval["previous_status"] == "needs_approval"
    assert approval["previous_next_action"] == "wait_for_human_approval"
    assert approval["approval_required"] is True
    assert approval["approval_reasons"] == ["paid_provider_requested"]
    assert approval["decision"] == "approved"
    assert approval["next_action"] == "return_cited_ad_package"
    assert approval["post_approval_worker_resumed"] is True
    assert approval["post_approval_worker_status"] == "succeeded"
    assert approval["post_approval_status"] == "completed"
    assert approval["copy_backend"] == "mock"
    assert approval["image_backend"] == "mock"
    assert approval["copy_option_count"] == 3
    assert len(approval["reviewer_id_sha256"]) == 64
    assert len(approval["comment_sha256"]) == 64
    assert approval["audit_persisted"] is False
    assert approval["raw_inputs_committed"] is False

    serialized = json.dumps(approval, ensure_ascii=False)
    for raw_value in [
        "비공개 말차 푸딩",
        "VIP 고객에게만 보일 문구",
        "reviewer@example.com",
        "VIP 고객 원문이 담긴 비공개 승인 메모",
    ]:
        assert raw_value not in serialized


def test_agentic_rag_run_approval_uses_redacted_cross_process_resume_without_pending_context(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import api.main as api_main

    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("GENERATION_LOG_PATH", str(tmp_path / "generations.jsonl"))
    monkeypatch.setenv(
        "AGENTIC_RAG_CHECKPOINT_DB",
        str(tmp_path / "agentic-rag-checkpoints.sqlite"),
    )
    monkeypatch.setattr(api_main, "_agentic_rag_requires_paid_provider", lambda deps: True)
    payload = {
        **base_payload(),
        "product_name": "비공개 말차 푸딩",
        "user_constraints": "VIP 고객에게만 보일 문구",
    }

    with client.stream("POST", "/agentic-rag/runs/stream", json=payload) as response:
        body = response.read().decode("utf-8")

    assert response.status_code == 200
    run_id = _parse_sse_events(body)[0]["data"]["run_id"]
    with api_main._AGENTIC_RAG_PENDING_APPROVAL_RUNS_LOCK:
        api_main._AGENTIC_RAG_PENDING_APPROVAL_RUNS.clear()

    approval_response = client.post(
        f"/agentic-rag/runs/{run_id}/approval",
        json={
            "decision": "approved",
            "reviewer_id": "reviewer@example.com",
            "comment": "VIP 고객 원문이 담긴 비공개 승인 메모",
        },
    )

    assert approval_response.status_code == 200
    approval = approval_response.json()
    assert approval["next_action"] == "return_cited_ad_package"
    assert approval["post_approval_worker_resumed"] is True
    assert approval["post_approval_resume_source"] == "redacted_sqlite_replay"
    assert approval["post_approval_worker_status"] == "succeeded"
    assert approval["post_approval_status"] == "completed"
    assert approval["copy_backend"] == "mock"
    assert approval["image_backend"] == "mock"
    assert approval["copy_option_count"] == 3
    assert approval["used_reference"] is False
    assert approval["raw_inputs_committed"] is False

    serialized = json.dumps(approval, ensure_ascii=False)
    for raw_value in [
        "비공개 말차 푸딩",
        "VIP 고객에게만 보일 문구",
        "reviewer@example.com",
        "VIP 고객 원문이 담긴 비공개 승인 메모",
    ]:
        assert raw_value not in serialized


def test_agentic_rag_run_approval_rejects_non_approval_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("GENERATION_LOG_PATH", str(tmp_path / "generations.jsonl"))
    monkeypatch.setenv(
        "AGENTIC_RAG_CHECKPOINT_DB",
        str(tmp_path / "agentic-rag-checkpoints.sqlite"),
    )

    with client.stream("POST", "/agentic-rag/runs/stream", json=base_payload()) as response:
        body = response.read().decode("utf-8")

    assert response.status_code == 200
    run_id = _parse_sse_events(body)[0]["data"]["run_id"]
    approval_response = client.post(
        f"/agentic-rag/runs/{run_id}/approval",
        json={"decision": "approved"},
    )

    assert approval_response.status_code == 409
    assert approval_response.json()["detail"] == "Agentic RAG run is not waiting for approval."


def test_agentic_rag_run_rejection_does_not_resume_worker(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import api.main as api_main

    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("GENERATION_LOG_PATH", str(tmp_path / "generations.jsonl"))
    monkeypatch.setenv(
        "AGENTIC_RAG_CHECKPOINT_DB",
        str(tmp_path / "agentic-rag-checkpoints.sqlite"),
    )
    monkeypatch.setattr(api_main, "_agentic_rag_requires_paid_provider", lambda deps: True)

    with client.stream("POST", "/agentic-rag/runs/stream", json=base_payload()) as response:
        body = response.read().decode("utf-8")

    assert response.status_code == 200
    run_id = _parse_sse_events(body)[0]["data"]["run_id"]

    approval_response = client.post(
        f"/agentic-rag/runs/{run_id}/approval",
        json={"decision": "rejected", "reviewer_id": "reviewer@example.com"},
    )

    assert approval_response.status_code == 200
    approval = approval_response.json()
    assert approval["status"] == "rejected"
    assert approval["next_action"] == "stop_run_without_worker"
    assert approval["post_approval_worker_resumed"] is False
    assert "post_approval_worker_status" not in approval


def test_agentic_rag_run_stream_uses_workflow_tracer_for_graph_nodes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import api.main as api_main
    from dessert_ad_studio.observability import InMemoryWorkflowTracer

    tracer = InMemoryWorkflowTracer()
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("GENERATION_LOG_PATH", str(tmp_path / "generations.jsonl"))
    monkeypatch.setattr(api_main, "build_workflow_tracer", lambda: tracer)
    payload = {
        **base_payload(),
        "product_name": "비공개 말차 푸딩",
        "user_constraints": "VIP 고객에게만 보일 문구",
    }

    with client.stream("POST", "/agentic-rag/runs/stream", json=payload) as response:
        body = response.read().decode("utf-8")

    assert response.status_code == 200
    assert [
        record.name for record in tracer.records() if record.name.startswith("agentic_rag.")
    ] == [
        "agentic_rag.plan_campaign",
        "agentic_rag.run_tool_suite",
        "agentic_rag.retrieve_context",
        "agentic_rag.build_citations",
        "agentic_rag.guardrail_check",
        "agentic_rag.execute_worker",
        "agentic_rag.finalize",
    ]

    serialized = json.dumps([record.attributes for record in tracer.records()], ensure_ascii=False)
    assert "비공개 말차 푸딩" not in serialized
    assert "VIP 고객에게만 보일 문구" not in serialized
    assert "비공개 말차 푸딩" not in body
    assert "VIP 고객에게만 보일 문구" not in body


def test_agentic_rag_run_stream_routes_paid_provider_to_approval(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import api.main as api_main

    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("GENERATION_LOG_PATH", str(tmp_path / "generations.jsonl"))
    monkeypatch.setenv(
        "AGENTIC_RAG_CHECKPOINT_DB",
        str(tmp_path / "agentic-rag-checkpoints.sqlite"),
    )
    monkeypatch.setattr(api_main, "_agentic_rag_requires_paid_provider", lambda deps: True)

    with client.stream("POST", "/agentic-rag/runs/stream", json=base_payload()) as response:
        body = response.read().decode("utf-8")

    assert response.status_code == 200
    events = _parse_sse_events(body)
    assert [
        event["data"].get("node") for event in events if event["event"] == "node_completed"
    ] == [
        "plan_campaign",
        "run_tool_suite",
        "retrieve_context",
        "build_citations",
        "guardrail_check",
        "human_approval",
    ]
    assert events[-1]["data"] == {
        "status": "needs_approval",
        "next_action": "wait_for_human_approval",
        "raw_inputs_committed": False,
    }
    guardrail_event = next(
        event for event in events if event["data"].get("node") == "guardrail_check"
    )
    assert guardrail_event["data"] == {
        "node": "guardrail_check",
        "status": "needs_approval",
        "approval_required": True,
        "approval_reasons": ["paid_provider_requested"],
    }
    assert "execute_worker" not in body


def test_agentic_rag_run_websocket_emits_redacted_worker_events(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("GENERATION_LOG_PATH", str(tmp_path / "generations.jsonl"))
    payload = {
        **base_payload(),
        "product_name": "비공개 말차 푸딩",
        "user_constraints": "VIP 고객에게만 보일 문구",
    }

    with client.websocket_connect("/agentic-rag/runs/ws") as websocket:
        websocket.send_json(payload)
        messages = _receive_agentic_rag_websocket_messages(websocket)

    assert [message["event"] for message in messages] == [
        "run_started",
        "node_completed",
        "node_completed",
        "node_completed",
        "node_completed",
        "node_completed",
        "node_completed",
        "node_completed",
        "run_completed",
    ]
    assert messages[0]["data"]["stream_protocol"] == "websocket"
    assert messages[0]["data"]["run_id"].startswith("agr-")
    assert messages[0]["data"]["raw_inputs_committed"] is False
    assert [
        message["data"].get("node") for message in messages if message["event"] == "node_completed"
    ] == [
        "plan_campaign",
        "run_tool_suite",
        "retrieve_context",
        "build_citations",
        "guardrail_check",
        "execute_worker",
        "finalize",
    ]
    finalize_message = next(
        message for message in messages if message["data"].get("node") == "finalize"
    )
    assert finalize_message["data"]["cited_ad_package_ready"] is True
    assert finalize_message["data"]["cited_ad_package_source_doc_count"] >= 1
    assert finalize_message["data"]["raw_assets_committed"] is False
    assert messages[-1]["data"] == {
        "status": "completed",
        "next_action": "return_cited_ad_package",
        "raw_inputs_committed": False,
    }

    serialized = json.dumps(messages, ensure_ascii=False)
    assert "비공개 말차 푸딩" not in serialized
    assert "VIP 고객에게만 보일 문구" not in serialized


def test_agentic_rag_run_websocket_routes_paid_provider_to_approval(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import api.main as api_main

    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("GENERATION_LOG_PATH", str(tmp_path / "generations.jsonl"))
    monkeypatch.setenv(
        "AGENTIC_RAG_CHECKPOINT_DB",
        str(tmp_path / "agentic-rag-checkpoints.sqlite"),
    )
    monkeypatch.setattr(api_main, "_agentic_rag_requires_paid_provider", lambda deps: True)

    with client.websocket_connect("/agentic-rag/runs/ws") as websocket:
        websocket.send_json(base_payload())
        messages = _receive_agentic_rag_websocket_messages(websocket)

    assert [
        message["data"].get("node") for message in messages if message["event"] == "node_completed"
    ] == [
        "plan_campaign",
        "run_tool_suite",
        "retrieve_context",
        "build_citations",
        "guardrail_check",
        "human_approval",
    ]
    assert messages[-1]["data"] == {
        "status": "needs_approval",
        "next_action": "wait_for_human_approval",
        "raw_inputs_committed": False,
    }
    assert not any(
        message["data"].get("node") == "execute_worker"
        for message in messages
        if message["event"] == "node_completed"
    )


def test_agentic_rag_run_websocket_accepts_approval_decision_and_resumes_worker(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import api.main as api_main

    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("GENERATION_LOG_PATH", str(tmp_path / "generations.jsonl"))
    monkeypatch.setenv(
        "AGENTIC_RAG_CHECKPOINT_DB",
        str(tmp_path / "agentic-rag-checkpoints.sqlite"),
    )
    monkeypatch.setattr(api_main, "_agentic_rag_requires_paid_provider", lambda deps: True)
    payload = {
        **base_payload(),
        "product_name": "비공개 말차 푸딩",
        "user_constraints": "VIP 고객에게만 보일 문구",
    }

    with client.websocket_connect("/agentic-rag/runs/ws") as websocket:
        websocket.send_json(payload)
        messages = _receive_agentic_rag_websocket_messages(websocket)
        run_id = messages[0]["data"]["run_id"]
        websocket.send_json(
            {
                "type": "approval_decision",
                "decision": "approved",
                "reviewer_id": "reviewer@example.com",
                "comment": "비공개 승인 메모",
            }
        )
        approval_messages = _receive_agentic_rag_websocket_messages_until(
            websocket,
            "approval_completed",
        )

    assert messages[-1]["data"] == {
        "status": "needs_approval",
        "next_action": "wait_for_human_approval",
        "raw_inputs_committed": False,
    }
    assert approval_messages[-1]["data"]["run_id"] == run_id
    assert approval_messages[-1]["data"]["status"] == "approved"
    assert approval_messages[-1]["data"]["next_action"] == "return_cited_ad_package"
    assert approval_messages[-1]["data"]["post_approval_worker_resumed"] is True
    assert approval_messages[-1]["data"]["post_approval_worker_status"] == "succeeded"
    assert approval_messages[-1]["data"]["raw_inputs_committed"] is False

    serialized = json.dumps([messages, approval_messages], ensure_ascii=False)
    for raw_value in [
        "비공개 말차 푸딩",
        "VIP 고객에게만 보일 문구",
        "reviewer@example.com",
        "비공개 승인 메모",
    ]:
        assert raw_value not in serialized


def test_create_generation_job_runs_inline_and_status_is_redacted(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import api.main as api_main

    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("GENERATION_QUEUE_BACKEND", "inline")
    monkeypatch.setenv("GENERATION_HISTORY_BACKEND", "memory")
    monkeypatch.delenv("GENERATION_HISTORY_DSN", raising=False)
    api_main.get_generation_job_store.cache_clear()

    response = client.post("/generation-jobs", json=base_payload())

    assert response.status_code == 202
    accepted = response.json()
    assert accepted["queue_backend"] == "inline"
    assert accepted["status_url"].startswith("/generation-jobs/")

    status_response = client.get(accepted["status_url"])

    assert status_response.status_code == 200
    status = status_response.json()
    assert status["job_id"] == accepted["job_id"]
    assert status["status"] == "succeeded"
    assert status["request_summary"]["campaign_purpose"] == "new_menu"
    assert status["request_summary"]["has_user_constraints"] is True
    assert "product_name" not in status["request_summary"]
    assert "user_constraints" not in status["request_summary"]
    assert status["response_summary"]["copy_options_count"] == 3
    assert "copy_options" not in status["response_summary"]
    assert "prompt_summary" not in status["response_summary"]


def test_create_generation_job_rejects_reference_image_payload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import api.main as api_main

    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("GENERATION_QUEUE_BACKEND", "inline")
    monkeypatch.setenv("GENERATION_HISTORY_BACKEND", "memory")
    api_main.get_generation_job_store.cache_clear()
    payload = {**base_payload(), "reference_image_b64": tiny_png_b64()}

    response = client.post("/generation-jobs", json=payload)

    assert response.status_code == 400
    assert "비동기 생성 작업은 아직 참고 이미지를 지원하지 않습니다" in response.json()["detail"]


def test_generation_job_status_returns_404_for_unknown_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.main as api_main

    monkeypatch.setenv("GENERATION_HISTORY_BACKEND", "memory")
    api_main.get_generation_job_store.cache_clear()

    response = client.get("/generation-jobs/job-missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "generation job not found"


def test_generation_job_policy_reports_explicit_async_limits() -> None:
    response = client.get("/generation-jobs/policy")

    assert response.status_code == 200
    assert response.json() == {
        "cancel_supported": False,
        "automatic_retries": 0,
        "worker_job_timeout_seconds": None,
        "dead_letter_queue_supported": False,
        "reference_image_async_supported": False,
        "policy": "explicit_non_support_until_storage_and_retry_policy_are_selected",
    }


def test_cancel_generation_job_is_explicit_non_support() -> None:
    response = client.post("/generation-jobs/job-test/cancel")

    assert response.status_code == 501
    assert response.json()["detail"] == (
        "비동기 생성 작업 취소는 아직 지원하지 않습니다. "
        "재시도/타임아웃/취소 정책이 정해지기 전까지 상태 조회만 제공합니다."
    )


def test_generate_with_reference_image_flags_usage() -> None:
    payload = {
        **base_payload(),
        "reference_image_b64": tiny_png_b64(),
        "reference_image_name": "store_photo.png",
    }

    response = client.post("/generate", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["used_reference"] is True
    assert body["prompt_summary"].splitlines()[0] == (
        "업로드된 제품 사진의 피사체와 구도를 보존하면서 광고 이미지로 연출한다."
    )


def test_generate_includes_product_analysis(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    response = client.post("/generate", json=base_payload())

    assert response.status_code == 200
    analysis = response.json()["product_analysis"]
    assert analysis["label"] == "Product analysis"
    assert analysis["analyzer_backend"] == "mock"
    assert "말차 푸딩" in analysis["product_context"]
    assert "참고 이미지 없음" in analysis["photo_strategy"]


def test_generate_ignores_reference_name_without_image_bytes(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    payload = {**base_payload(), "reference_image_name": "cake.png"}

    response = client.post("/generate", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["used_reference"] is False
    assert "참고 이미지 없음" in body["product_analysis"]["photo_strategy"]


def test_generate_product_analysis_reflects_reference_image(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    payload = {
        **base_payload(),
        "reference_image_b64": tiny_png_b64(),
        "reference_image_name": "cake.png",
    }
    response = client.post("/generate", json=payload)

    assert response.status_code == 200
    assert "업로드된 제품 사진" in response.json()["product_analysis"]["photo_strategy"]


def test_generate_rejects_unknown_product_analysis_backend(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("PRODUCT_ANALYSIS_BACKEND", "vlm")

    response = client.post("/generate", json=base_payload())

    assert response.status_code == 501
    assert response.json()["detail"] == "unknown product analysis backend: vlm"


def test_readyz_accepts_openai_product_analysis_backend_without_calling_api(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("PRODUCT_ANALYSIS_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json()["product_analysis_backend"] == "openai"


def test_generate_rejects_reference_image_for_flux2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IMAGE_BACKEND", "flux2")
    payload = {
        **base_payload(),
        "reference_image_b64": tiny_png_b64(),
        "reference_image_name": "store_photo.png",
    }

    response = client.post("/generate", json=payload)

    assert response.status_code == 400
    assert "참고 이미지" in response.json()["detail"]


def test_flux2_reference_rejection_spends_no_copy_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    from dessert_ad_studio.backends.mock import MockAdBackend

    def fail_if_called(self, request, **kwargs):
        raise AssertionError("copy backend must not be called when the reference is rejected")

    monkeypatch.setattr(MockAdBackend, "generate_copy", fail_if_called)
    monkeypatch.setenv("IMAGE_BACKEND", "flux2")
    payload = {**base_payload(), "reference_image_b64": tiny_png_b64()}

    response = client.post("/generate", json=payload)

    assert response.status_code == 400


def test_generate_rejects_invalid_reference_encoding() -> None:
    payload = {**base_payload(), "reference_image_b64": "not-base64!!!"}

    response = client.post("/generate", json=payload)

    assert response.status_code == 400
    assert "base64" in response.json()["detail"]


def test_generate_reports_missing_copy_backend_before_invalid_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COPY_BACKEND", "missing")
    payload = {**base_payload(), "reference_image_b64": "not-base64!!!"}

    response = client.post("/generate", json=payload)

    assert response.status_code == 501
    assert response.json()["detail"] == "unknown copy backend: missing"


def test_generate_maps_missing_openai_key_to_503(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPY_BACKEND", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    response = client.post("/generate", json=base_payload())

    assert response.status_code == 503
    assert "OPENAI_API_KEY" in response.json()["detail"]


def test_generate_preserves_backend_error_status_code(monkeypatch: pytest.MonkeyPatch) -> None:
    from dessert_ad_studio.backends.base import AdBackendError
    from dessert_ad_studio.backends.mock import MockAdBackend

    def fail_with_validation_error(self, request, **kwargs):
        raise AdBackendError("bad input", status_code=422)

    monkeypatch.setattr(MockAdBackend, "generate_copy", fail_with_validation_error)

    response = client.post("/generate", json=base_payload())

    assert response.status_code == 422
    assert response.json()["detail"] == "bad input"


def test_generate_maps_required_triton_template_failure_to_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.main as api_main

    class FailingTemplateScorer:
        def rank(self, request):
            raise RuntimeError("template scoring unavailable")

    monkeypatch.setenv("REQUIRE_TRITON", "1")
    monkeypatch.setattr(api_main, "get_template_scorer", lambda: FailingTemplateScorer())

    response = client.post("/generate", json=base_payload())

    assert response.status_code == 503
    assert "Triton template scoring failed" in response.json()["detail"]


def test_generate_rejects_unknown_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IMAGE_BACKEND", "unknown-backend")

    response = client.post("/generate", json=base_payload())

    assert response.status_code == 501


def test_generate_logs_usage_from_returned_results(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """JSONL usage must come from each request's own result objects, not from
    attributes on the cached (shared) backend instances."""
    import api.main as api_main
    from dessert_ad_studio.backends.base import CopyResult, ImageResult
    from dessert_ad_studio.schemas import CopyOption

    log_path = tmp_path / "generations.jsonl"
    monkeypatch.setenv("GENERATION_LOG_PATH", str(log_path))

    class FakeCopyBackend:
        name = "fake-copy"
        model_id = "fake-copy-model"

        def generate_copy(self, request, **kwargs):
            options = [
                CopyOption(headline=f"헤드라인 {i}", body="본문", call_to_action="행동 유도")
                for i in range(3)
            ]
            return CopyResult(
                options=options,
                usage={"prompt_tokens": 11, "completion_tokens": 22, "total_tokens": 33},
            )

    class FakeImageBackend:
        name = "fake-image"
        model_id = "fake-image-model"
        supports_reference_image = True

        def generate_image(self, request, image_prompt, reference_image=None):
            path = tmp_path / "fake.png"
            path.write_bytes(b"png")
            return ImageResult(path=str(path), usage={"total_tokens": 44})

    monkeypatch.setattr(api_main, "_copy_backend_for", lambda name, output_dir: FakeCopyBackend())
    monkeypatch.setattr(api_main, "_image_backend_for", lambda name, output_dir: FakeImageBackend())

    response = client.post("/generate", json=base_payload())

    assert response.status_code == 200
    record = json.loads(log_path.read_text(encoding="utf-8").splitlines()[-1])
    assert record["copy_usage"] == {
        "prompt_tokens": 11,
        "completion_tokens": 22,
        "total_tokens": 33,
    }
    assert record["image_usage"] == {"total_tokens": 44}


def test_image_failure_still_logs_spent_copy_usage(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """When the image call fails after copy succeeded, the spent copy tokens
    must still land in the quota log even though the request returns 5xx."""
    import api.main as api_main
    from dessert_ad_studio.backends.base import AdBackendError, CopyResult
    from dessert_ad_studio.schemas import CopyOption

    log_path = tmp_path / "generations.jsonl"
    monkeypatch.setenv("GENERATION_LOG_PATH", str(log_path))

    class FakeCopyBackend:
        name = "fake-copy"
        model_id = "fake-copy-model"

        def generate_copy(self, request, **kwargs):
            options = [
                CopyOption(headline=f"헤드라인 {i}", body="본문", call_to_action="행동 유도")
                for i in range(3)
            ]
            return CopyResult(
                options=options,
                usage={"prompt_tokens": 11, "completion_tokens": 22, "total_tokens": 33},
            )

    class FailingImageBackend:
        name = "failing-image"
        model_id = "failing-image-model"
        supports_reference_image = True

        def generate_image(self, request, image_prompt, reference_image=None):
            raise AdBackendError("이미지 생성 API 호출에 실패했습니다: boom")

    monkeypatch.setattr(api_main, "_copy_backend_for", lambda name, output_dir: FakeCopyBackend())
    monkeypatch.setattr(
        api_main, "_image_backend_for", lambda name, output_dir: FailingImageBackend()
    )

    response = client.post("/generate", json=base_payload())

    assert response.status_code == 503
    record = json.loads(log_path.read_text(encoding="utf-8").splitlines()[-1])
    assert record["copy_usage"] == {
        "prompt_tokens": 11,
        "completion_tokens": 22,
        "total_tokens": 33,
    }
    assert record["error"] == "이미지 생성 API 호출에 실패했습니다: boom"
    assert record["has_image_path"] is False
    assert record["image_path_sha256"] is None
    assert record["image_usage"] is None


def test_image_failure_log_uses_privacy_allowlist(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import api.main as api_main
    from dessert_ad_studio.backends.base import AdBackendError, CopyResult
    from dessert_ad_studio.schemas import CopyOption

    log_path = tmp_path / "generations.jsonl"
    monkeypatch.setenv("GENERATION_LOG_PATH", str(log_path))

    class FakeCopyBackend:
        name = "fake-copy"
        model_id = "fake-copy-model"

        def generate_copy(self, request, **kwargs):
            return CopyResult(
                options=[
                    CopyOption(
                        headline="비공개 헤드라인",
                        body="비공개 본문",
                        call_to_action="구매하기",
                    )
                ],
                usage={"total_tokens": 33},
            )

    class FailingImageBackend:
        name = "failing-image"
        model_id = "failing-image-model"
        supports_reference_image = True

        def generate_image(self, request, image_prompt, reference_image=None):
            raise AdBackendError("이미지 생성 API 호출에 실패했습니다: boom")

    monkeypatch.setattr(api_main, "_copy_backend_for", lambda name, output_dir: FakeCopyBackend())
    monkeypatch.setattr(
        api_main, "_image_backend_for", lambda name, output_dir: FailingImageBackend()
    )
    payload = {
        **base_payload(),
        "product_name": "비공개 말차 푸딩",
        "user_constraints": "VIP 고객에게만 보일 문구",
        "revision_request": "비공개 할인 강조",
        "reference_image_b64": tiny_png_b64(),
        "reference_image_name": "secret-reference.png",
    }

    response = client.post("/generate", json=payload)

    assert response.status_code == 503
    record = json.loads(log_path.read_text(encoding="utf-8").splitlines()[-1])
    serialized = json.dumps(record, ensure_ascii=False)
    for raw_value in [
        "비공개 말차 푸딩",
        "VIP 고객에게만 보일 문구",
        "비공개 할인 강조",
        "secret-reference.png",
        "비공개 헤드라인",
        "비공개 본문",
    ]:
        assert raw_value not in serialized
    assert "reference_image_name" not in record
    assert "image_path" not in record
    assert record["has_reference_image_name"] is True
    assert len(record["reference_image_name_sha256"]) == 64
    assert record["has_image_path"] is False
    assert record["image_path_sha256"] is None
    assert record["image_usage"] is None


def test_copy_failure_logs_no_row(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """If copy itself fails there is no usage to attribute — no row is written."""
    import api.main as api_main
    from dessert_ad_studio.backends.base import AdBackendError

    log_path = tmp_path / "generations.jsonl"
    monkeypatch.setenv("GENERATION_LOG_PATH", str(log_path))

    class FailingCopyBackend:
        name = "failing-copy"
        model_id = "failing-copy-model"

        def generate_copy(self, request, **kwargs):
            raise AdBackendError("문구 생성 API 호출에 실패했습니다: boom")

    monkeypatch.setattr(
        api_main, "_copy_backend_for", lambda name, output_dir: FailingCopyBackend()
    )

    response = client.post("/generate", json=base_payload())

    assert response.status_code == 503
    assert not log_path.exists()


def test_generate_survives_log_write_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    from dessert_ad_studio.generation_logger import GenerationLogger

    monkeypatch.setattr(
        GenerationLogger, "write", lambda self, record: (_ for _ in ()).throw(OSError("disk full"))
    )

    response = client.post("/generate", json=base_payload())

    assert response.status_code == 200


def test_template_scorer_defaults_to_local_without_require_triton(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without REQUIRE_TRITON=1 the scorer must be local from the start, so
    Triton-less deployments never pay a per-request connection failure."""
    import api.main as api_main
    from dessert_ad_studio.triton import LocalTemplateScorer

    monkeypatch.delenv("REQUIRE_TRITON", raising=False)

    assert isinstance(api_main.get_template_scorer(), LocalTemplateScorer)


def test_template_scorer_uses_triton_when_required(monkeypatch: pytest.MonkeyPatch) -> None:
    import api.main as api_main
    from dessert_ad_studio.triton import TritonTemplateScorer

    monkeypatch.setenv("REQUIRE_TRITON", "1")

    assert isinstance(api_main.get_template_scorer(), TritonTemplateScorer)


def test_a2a_agent_card() -> None:
    response = client.get("/.well-known/agent-card.json")

    assert response.status_code == 200
    card = response.json()
    assert card["name"] == "Dessert Ad Studio Agent"
    assert card["skills"][0]["id"] == "generate_ad_banner"
    assert card["supportedInterfaces"][0]["protocolBinding"] == "HTTP+JSON"


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
    assert "data part" in response.json()["detail"]


def test_a2a_send_message_preserves_backend_error_status_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dessert_ad_studio.backends.base import AdBackendError
    from dessert_ad_studio.backends.mock import MockAdBackend

    def fail_with_validation_error(self, request, **kwargs):
        raise AdBackendError("bad input", status_code=422)

    monkeypatch.setattr(MockAdBackend, "generate_copy", fail_with_validation_error)

    response = client.post(
        "/message:send",
        json={
            "message": {
                "role": "ROLE_USER",
                "messageId": "msg-3",
                "parts": [{"data": base_payload()}],
            }
        },
        headers={"content-type": "application/a2a+json"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "bad input"


def test_a2a_send_message_rejects_invalid_reference_encoding() -> None:
    payload = {**base_payload(), "reference_image_b64": "not-base64!!!"}

    response = client.post(
        "/message:send",
        json={
            "message": {
                "role": "ROLE_USER",
                "messageId": "msg-4",
                "parts": [{"data": payload}],
            }
        },
        headers={"content-type": "application/a2a+json"},
    )

    assert response.status_code == 400
    assert "base64" in response.json()["detail"]


def test_a2a_send_message_rejects_unsupported_reference_before_copy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dessert_ad_studio.backends.mock import MockAdBackend

    def fail_if_called(self, request, **kwargs):
        raise AssertionError("copy backend must not be called when the reference is rejected")

    monkeypatch.setattr(MockAdBackend, "generate_copy", fail_if_called)
    monkeypatch.setenv("IMAGE_BACKEND", "flux2")
    payload = {**base_payload(), "reference_image_b64": tiny_png_b64()}

    response = client.post(
        "/message:send",
        json={
            "message": {
                "role": "ROLE_USER",
                "messageId": "msg-5",
                "parts": [{"data": payload}],
            }
        },
        headers={"content-type": "application/a2a+json"},
    )

    assert response.status_code == 400
    assert "참고 이미지" in response.json()["detail"]


def test_a2a_get_missing_task_returns_404() -> None:
    response = client.get("/tasks/task-missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "A2A task not found"
