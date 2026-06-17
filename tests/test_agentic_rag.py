import json

from langgraph.checkpoint.memory import InMemorySaver

from dessert_ad_studio import agentic_rag as agentic_rag_module
from dessert_ad_studio.agentic_rag import (
    build_agentic_rag_graph,
    build_agentic_rag_initial_state,
)
from dessert_ad_studio.observability import InMemoryWorkflowTracer
from dessert_ad_studio.schemas import GenerationRequest


def sensitive_request() -> GenerationRequest:
    return GenerationRequest(
        campaign_purpose="new_menu",
        product_name="비공개 말차 푸딩",
        tone="premium",
        template_hint="minimal_premium",
        price_text="7,500원",
        user_constraints="VIP 고객에게만 보일 문구",
        revision_request="비공개 할인 강조",
        reference_image_b64="c2VjcmV0LWltYWdlLWJ5dGVz",
        reference_image_name="secret-reference.png",
    )


def test_agentic_rag_graph_routes_paid_provider_to_human_approval_without_raw_inputs():
    checkpointer = InMemorySaver()
    worker_calls: list[dict] = []

    def worker_executor(state: dict) -> dict:
        worker_calls.append(state)
        return {"status": "succeeded"}

    graph = build_agentic_rag_graph(
        checkpointer=checkpointer,
        worker_executor=worker_executor,
    )
    state = build_agentic_rag_initial_state(
        sensitive_request(),
        requires_paid_provider=True,
        estimated_cost_usd=0.12,
        approval_cost_threshold_usd=0.10,
    )

    result = graph.invoke(state, {"configurable": {"thread_id": "paid-provider-test"}})

    assert result["status"] == "needs_approval"
    assert result["next_action"] == "wait_for_human_approval"
    assert result["approval"] == {
        "required": True,
        "reasons": ["paid_provider_requested", "estimated_cost_exceeds_threshold"],
    }
    assert worker_calls == []
    assert result["node_trace"] == [
        "plan_campaign",
        "retrieve_context",
        "build_citations",
        "guardrail_check",
        "human_approval",
    ]
    assert result["marketing_context"]["retrieved_docs_count"] >= 1
    assert result["citations"]
    assert result["citations"][0]["source_doc_id"].startswith("guide-")
    assert list(checkpointer.list({"configurable": {"thread_id": "paid-provider-test"}}))

    serialized = json.dumps(result, ensure_ascii=False)
    for raw_value in [
        "비공개 말차 푸딩",
        "VIP 고객에게만 보일 문구",
        "비공개 할인 강조",
        "secret-reference.png",
        "c2VjcmV0LWltYWdlLWJ5dGVz",
    ]:
        assert raw_value not in serialized
    assert result["request_summary"]["has_reference_image"] is True
    assert len(result["request_summary"]["product_name_sha256"]) == 64
    assert len(result["request_summary"]["reference_image_name_sha256"]) == 64


def test_agentic_rag_graph_executes_worker_after_guardrail_clear_without_raw_inputs():
    worker_calls: list[dict] = []

    def worker_executor(state: dict) -> dict:
        worker_calls.append(state)
        return {
            "status": "succeeded",
            "copy_backend": "mock",
            "image_backend": "mock",
            "copy_option_count": 3,
            "used_reference": False,
            "elapsed_ms": 18.5,
            "workflow_trace_steps": ["rank_templates", "generate_copy", "generate_image"],
        }

    graph = build_agentic_rag_graph(worker_executor=worker_executor)
    state = build_agentic_rag_initial_state(
        GenerationRequest(
            campaign_purpose="brand_awareness",
            product_name="비공개 딸기 크림 크루아상",
            tone="warm",
            template_hint="cozy_cafe",
            user_constraints="VIP 촬영본으로 인스타그램 피드용",
        ),
        requires_paid_provider=False,
        estimated_cost_usd=0.0,
        approval_cost_threshold_usd=0.10,
    )

    result = graph.invoke(state)

    assert len(worker_calls) == 1
    assert result["status"] == "completed"
    assert result["next_action"] == "return_cited_ad_package"
    assert result["worker_result"] == {
        "status": "succeeded",
        "copy_backend": "mock",
        "image_backend": "mock",
        "copy_option_count": 3,
        "used_reference": False,
        "elapsed_ms": 18.5,
        "workflow_trace_steps": ["rank_templates", "generate_copy", "generate_image"],
    }
    assert result["node_trace"] == [
        "plan_campaign",
        "retrieve_context",
        "build_citations",
        "guardrail_check",
        "execute_worker",
        "finalize",
    ]

    serialized = json.dumps(result, ensure_ascii=False)
    assert "비공개 딸기 크림 크루아상" not in serialized
    assert "VIP 촬영본" not in serialized


def test_agentic_rag_graph_reflects_and_retries_worker_failure_without_error_detail():
    attempts = 0

    def worker_executor(state: dict) -> dict:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("raw provider error with private customer text")
        return {
            "status": "succeeded",
            "copy_backend": "mock",
            "image_backend": "mock",
            "copy_option_count": 3,
            "used_reference": False,
            "elapsed_ms": 22.0,
            "workflow_trace_steps": ["rank_templates", "generate_copy", "generate_image"],
        }

    graph = build_agentic_rag_graph(worker_executor=worker_executor)
    state = build_agentic_rag_initial_state(
        GenerationRequest(
            campaign_purpose="new_menu",
            product_name="말차 푸딩",
            tone="clean",
            template_hint="minimal_premium",
        ),
        requires_paid_provider=False,
        estimated_cost_usd=0.0,
        approval_cost_threshold_usd=0.10,
    )

    result = graph.invoke(state)

    assert attempts == 2
    assert result["status"] == "completed"
    assert result["reflection"] == {
        "attempts": 1,
        "last_error_type": "RuntimeError",
        "retry_budget": 1,
    }
    assert result["node_trace"] == [
        "plan_campaign",
        "retrieve_context",
        "build_citations",
        "guardrail_check",
        "execute_worker",
        "reflect_on_worker_failure",
        "execute_worker",
        "finalize",
    ]

    serialized = json.dumps(result, ensure_ascii=False)
    assert "raw provider error" not in serialized
    assert "private customer text" not in serialized


def test_agentic_rag_graph_routes_low_cost_local_run_to_worker():
    graph = build_agentic_rag_graph()
    state = build_agentic_rag_initial_state(
        GenerationRequest(
            campaign_purpose="brand_awareness",
            product_name="딸기 크림 크루아상",
            tone="warm",
            template_hint="cozy_cafe",
            user_constraints="인스타그램 피드용",
        ),
        requires_paid_provider=False,
        estimated_cost_usd=0.0,
        approval_cost_threshold_usd=0.10,
    )

    result = graph.invoke(state)

    assert result["status"] == "ready_for_worker"
    assert result["next_action"] == "dispatch_generation_worker"
    assert result["approval"] == {"required": False, "reasons": []}
    assert result["node_trace"] == [
        "plan_campaign",
        "retrieve_context",
        "build_citations",
        "guardrail_check",
        "finalize",
    ]
    assert result["plan"]["worker"] == "generation_workflow"
    assert result["marketing_context"]["retriever_backend"] == "keyword"
    assert result["citations"]


def test_agentic_rag_sqlite_checkpointer_persists_redacted_checkpoints(tmp_path):
    assert hasattr(agentic_rag_module, "open_agentic_rag_sqlite_checkpointer")

    db_path = tmp_path / "agentic-rag-checkpoints.sqlite"
    config = {"configurable": {"thread_id": "sqlite-worker-route"}}
    worker_calls: list[dict] = []

    def worker_executor(state: dict) -> dict:
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

    state = build_agentic_rag_initial_state(
        sensitive_request(),
        requires_paid_provider=False,
        estimated_cost_usd=0.0,
        approval_cost_threshold_usd=0.10,
    )

    with agentic_rag_module.open_agentic_rag_sqlite_checkpointer(db_path) as checkpointer:
        graph = build_agentic_rag_graph(
            checkpointer=checkpointer,
            worker_executor=worker_executor,
        )
        result = graph.invoke(state, config)
        checkpoints = list(checkpointer.list(config))

    assert len(worker_calls) == 1
    assert result["status"] == "completed"
    assert result["next_action"] == "return_cited_ad_package"
    assert db_path.exists()
    assert len(checkpoints) >= 1

    with agentic_rag_module.open_agentic_rag_sqlite_checkpointer(db_path) as checkpointer:
        persisted_checkpoints = list(checkpointer.list(config))

    assert len(persisted_checkpoints) == len(checkpoints)

    checkpoint_bytes = db_path.read_bytes()
    for raw_value in [
        "비공개 말차 푸딩",
        "VIP 고객에게만 보일 문구",
        "비공개 할인 강조",
        "secret-reference.png",
        "c2VjcmV0LWltYWdlLWJ5dGVz",
    ]:
        assert raw_value.encode("utf-8") not in checkpoint_bytes


def test_agentic_rag_graph_emits_redacted_openinference_spans():
    tracer = InMemoryWorkflowTracer()

    def worker_executor(_state: dict) -> dict:
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

    assert result["status"] == "completed"
    records = tracer.records()
    assert [record.name for record in records] == [
        "agentic_rag.plan_campaign",
        "agentic_rag.retrieve_context",
        "agentic_rag.build_citations",
        "agentic_rag.guardrail_check",
        "agentic_rag.execute_worker",
        "agentic_rag.finalize",
    ]
    assert [record.attributes["openinference.span.kind"] for record in records] == [
        "AGENT",
        "RETRIEVER",
        "CHAIN",
        "GUARDRAIL",
        "TOOL",
        "CHAIN",
    ]
    assert records[0].attributes["agentic_rag.node"] == "plan_campaign"
    assert records[-1].attributes["agentic_rag.status"] == "completed"
    assert records[-1].attributes["agentic_rag.next_action"] == "return_cited_ad_package"

    serialized = json.dumps([record.attributes for record in records], ensure_ascii=False)
    assert "비공개 말차 푸딩" not in serialized
    assert "VIP 고객에게만 보일 문구" not in serialized
