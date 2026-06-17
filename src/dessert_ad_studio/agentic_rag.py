from __future__ import annotations

from hashlib import sha256
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from dessert_ad_studio.marketing_context import KeywordMarketingContextRetriever
from dessert_ad_studio.schemas import (
    CampaignPurpose,
    GenerationRequest,
    ProductAnalysis,
    TemplateHint,
    Tone,
)

AgenticRagStatus = Literal["planned", "context_ready", "needs_approval", "ready_for_worker"]
AgenticRagNextAction = Literal["wait_for_human_approval", "dispatch_generation_worker"]


class AgenticRagRequestSummary(TypedDict, total=False):
    campaign_purpose: CampaignPurpose
    tone: Tone
    template_hint: TemplateHint
    has_price_text: bool
    has_user_constraints: bool
    has_revision_request: bool
    has_reference_image: bool
    product_name_sha256: str
    user_constraints_sha256: str
    revision_request_sha256: str
    reference_image_name_sha256: str
    retrieval_query: str


class AgenticRagApproval(TypedDict):
    required: bool
    reasons: list[str]


class AgenticRagCitation(TypedDict):
    source_doc_id: str
    evidence_type: str
    supports: str


class AgenticRagState(TypedDict, total=False):
    request_summary: AgenticRagRequestSummary
    requires_paid_provider: bool
    estimated_cost_usd: float
    approval_cost_threshold_usd: float
    plan: dict[str, Any]
    marketing_context: dict[str, Any]
    citations: list[AgenticRagCitation]
    approval: AgenticRagApproval
    status: AgenticRagStatus
    next_action: AgenticRagNextAction
    node_trace: list[str]


def build_agentic_rag_initial_state(
    request: GenerationRequest,
    *,
    requires_paid_provider: bool,
    estimated_cost_usd: float,
    approval_cost_threshold_usd: float,
) -> AgenticRagState:
    """Build checkpoint-safe graph input from a potentially sensitive request."""

    request_summary: AgenticRagRequestSummary = {
        "campaign_purpose": request.campaign_purpose,
        "tone": request.tone,
        "template_hint": request.template_hint,
        "has_price_text": bool(request.price_text),
        "has_user_constraints": bool(request.user_constraints),
        "has_revision_request": bool(request.revision_request),
        "has_reference_image": request.reference_image_b64 is not None,
        "product_name_sha256": _hash_text(request.product_name),
        "retrieval_query": " ".join(_safe_retrieval_terms(request)),
    }
    if request.user_constraints:
        request_summary["user_constraints_sha256"] = _hash_text(request.user_constraints)
    if request.revision_request:
        request_summary["revision_request_sha256"] = _hash_text(request.revision_request)
    if request.reference_image_name:
        request_summary["reference_image_name_sha256"] = _hash_text(request.reference_image_name)

    return {
        "request_summary": request_summary,
        "requires_paid_provider": requires_paid_provider,
        "estimated_cost_usd": estimated_cost_usd,
        "approval_cost_threshold_usd": approval_cost_threshold_usd,
        "status": "planned",
        "node_trace": [],
    }


def build_agentic_rag_graph(*, checkpointer: Any | None = None) -> Any:
    workflow = StateGraph(AgenticRagState)
    workflow.add_node("plan_campaign", _plan_campaign)
    workflow.add_node("retrieve_context", _retrieve_context)
    workflow.add_node("build_citations", _build_citations)
    workflow.add_node("guardrail_check", _guardrail_check)
    workflow.add_node("human_approval", _human_approval)
    workflow.add_node("finalize", _finalize)

    workflow.add_edge(START, "plan_campaign")
    workflow.add_edge("plan_campaign", "retrieve_context")
    workflow.add_edge("retrieve_context", "build_citations")
    workflow.add_edge("build_citations", "guardrail_check")
    workflow.add_conditional_edges(
        "guardrail_check",
        _route_after_guardrail,
        {
            "human_approval": "human_approval",
            "finalize": "finalize",
        },
    )
    workflow.add_edge("human_approval", END)
    workflow.add_edge("finalize", END)
    return workflow.compile(checkpointer=checkpointer)


def _plan_campaign(state: AgenticRagState) -> dict[str, Any]:
    return {
        "plan": {
            "worker": "generation_workflow",
            "retrieval_strategy": "keyword_marketing_context",
            "tool_budget": {
                "max_tool_calls": 4,
                "planned_tools": [
                    "document_retrieval",
                    "citation_builder",
                    "guardrail_check",
                    "generation_workflow",
                ],
            },
            "reflection_budget": 1,
            "requires_paid_provider": state.get("requires_paid_provider", False),
        },
        "status": "planned",
        "node_trace": _trace_after(state, "plan_campaign"),
    }


def _retrieve_context(state: AgenticRagState) -> dict[str, Any]:
    summary = state["request_summary"]
    request = _sanitized_retrieval_request(summary)
    analysis = _sanitized_product_analysis(summary)
    marketing_context = KeywordMarketingContextRetriever().retrieve(request, analysis)
    return {
        "marketing_context": marketing_context.model_dump(),
        "status": "context_ready",
        "node_trace": _trace_after(state, "retrieve_context"),
    }


def _build_citations(state: AgenticRagState) -> dict[str, Any]:
    source_doc_ids = state.get("marketing_context", {}).get("source_doc_ids", [])
    citations = [
        {
            "source_doc_id": source_doc_id,
            "evidence_type": "marketing_context",
            "supports": "copy_guidance_or_policy_guardrail",
        }
        for source_doc_id in source_doc_ids
    ]
    return {
        "citations": citations,
        "node_trace": _trace_after(state, "build_citations"),
    }


def _guardrail_check(state: AgenticRagState) -> dict[str, Any]:
    reasons: list[str] = []
    if state.get("requires_paid_provider", False):
        reasons.append("paid_provider_requested")
    if state.get("estimated_cost_usd", 0.0) > state.get("approval_cost_threshold_usd", 0.0):
        reasons.append("estimated_cost_exceeds_threshold")
    return {
        "approval": {
            "required": bool(reasons),
            "reasons": reasons,
        },
        "status": "needs_approval" if reasons else "ready_for_worker",
        "node_trace": _trace_after(state, "guardrail_check"),
    }


def _route_after_guardrail(state: AgenticRagState) -> Literal["human_approval", "finalize"]:
    if state.get("approval", {}).get("required", False):
        return "human_approval"
    return "finalize"


def _human_approval(state: AgenticRagState) -> dict[str, Any]:
    return {
        "status": "needs_approval",
        "next_action": "wait_for_human_approval",
        "node_trace": _trace_after(state, "human_approval"),
    }


def _finalize(state: AgenticRagState) -> dict[str, Any]:
    return {
        "status": "ready_for_worker",
        "next_action": "dispatch_generation_worker",
        "node_trace": _trace_after(state, "finalize"),
    }


def _sanitized_retrieval_request(summary: AgenticRagRequestSummary) -> GenerationRequest:
    return GenerationRequest(
        campaign_purpose=summary["campaign_purpose"],
        product_name="dessert",
        tone=summary["tone"],
        template_hint=summary["template_hint"],
        user_constraints=summary["retrieval_query"],
    )


def _sanitized_product_analysis(summary: AgenticRagRequestSummary) -> ProductAnalysis:
    return ProductAnalysis(
        label="redacted_request_summary",
        product_context=summary["retrieval_query"],
        ad_goal=summary["campaign_purpose"],
        visual_strategy=summary["template_hint"],
        photo_strategy="reference_present"
        if summary.get("has_reference_image")
        else "no_reference",
        copy_focus=summary["tone"],
        rendering_strategy="existing_generation_workflow",
        analyzer_backend="agentic_rag_redacted_summary",
    )


def _safe_retrieval_terms(request: GenerationRequest) -> list[str]:
    terms = ["dessert", request.campaign_purpose, request.tone, request.template_hint]
    if request.template_hint in {"cozy_cafe", "cute_dessert"}:
        terms.append("카페")
    if request.template_hint == "minimal_premium" or request.tone == "premium":
        terms.append("premium")
    if request.campaign_purpose == "discount":
        terms.append("discount")
    if _mentions_instagram(request.user_constraints):
        terms.append("instagram")
    return terms


def _mentions_instagram(text: str) -> bool:
    normalized = text.lower()
    return "instagram" in normalized or "인스타" in normalized or "sns" in normalized


def _trace_after(state: AgenticRagState, node_name: str) -> list[str]:
    return [*state.get("node_trace", []), node_name]


def _hash_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()
