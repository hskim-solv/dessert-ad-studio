import base64
import io
import json
from pathlib import Path

from PIL import Image

from dessert_ad_studio.backends.base import CopyResult, ImageResult
from dessert_ad_studio.backends.mock import MockAdBackend
from dessert_ad_studio.observability import InMemoryWorkflowTracer
from dessert_ad_studio.product_analysis import MockProductAnalyzer
from dessert_ad_studio.schemas import (
    CopyOption,
    GenerationRequest,
    MarketingContext,
    ProductAnalysis,
    TemplateRanking,
)
from dessert_ad_studio.triton import LocalTemplateScorer
from dessert_ad_studio.workflow import GenerationWorkflowDependencies, run_generation_workflow


def request_payload() -> GenerationRequest:
    return GenerationRequest(
        campaign_purpose="new_menu",
        product_name="말차 푸딩",
        tone="clean",
        template_hint="minimal_premium",
        price_text="5,500원",
        user_constraints="깔끔한 프리미엄 느낌",
    )


def sensitive_request_payload() -> GenerationRequest:
    buffer = io.BytesIO()
    Image.new("RGB", (16, 16), color=(120, 200, 160)).save(buffer, format="PNG")
    return GenerationRequest(
        campaign_purpose="new_menu",
        product_name="비공개 말차 푸딩",
        tone="clean",
        template_hint="minimal_premium",
        price_text="5,500원",
        user_constraints="VIP 고객에게만 보일 문구",
        revision_request="비공개 할인 강조",
        reference_image_b64=base64.b64encode(buffer.getvalue()).decode("ascii"),
        reference_image_name="secret-reference.png",
    )


def test_workflow_returns_generation_response_and_trace(tmp_path: Path) -> None:
    backend = MockAdBackend(output_dir=str(tmp_path))
    deps = GenerationWorkflowDependencies(
        template_scorer=LocalTemplateScorer(),
        copy_backend=backend,
        image_backend=backend,
        product_analyzer=MockProductAnalyzer(),
        log_path=tmp_path / "generations.jsonl",
    )

    output = run_generation_workflow(request_payload(), deps)

    assert output.response.copy_backend == "mock"
    assert output.response.image_backend == "mock"
    assert output.response.product_analysis.analyzer_backend == "mock"
    assert output.response.image_path.endswith(".png")
    assert [entry.step for entry in output.trace] == [
        "rank_templates",
        "decode_reference",
        "analyze_product",
        "retrieve_marketing_context",
        "build_image_prompt",
        "generate_copy",
        "generate_image",
        "write_log",
    ]
    assert output.trace[-1].metadata["has_log_path"] is True
    assert len(output.trace[-1].metadata["log_path_sha256"]) == 64


class FakeTemplateScorer:
    def rank(self, request: GenerationRequest) -> TemplateRanking:
        return TemplateRanking(
            template_name=request.template_hint,
            score=0.9,
            scorer="fake-scorer",
            latency_ms=1.2,
        )


class FakeCopyBackend:
    name = "fake-copy"
    last_product_analysis: ProductAnalysis | None = None
    last_marketing_context: MarketingContext | None = None

    def generate_copy(
        self,
        request: GenerationRequest,
        *,
        product_analysis: ProductAnalysis | None = None,
        marketing_context: MarketingContext | None = None,
    ) -> CopyResult:
        self.last_product_analysis = product_analysis
        self.last_marketing_context = marketing_context
        return CopyResult(
            options=[
                CopyOption(headline="헤드라인", body="본문", call_to_action="방문하기"),
            ],
            usage={"total_tokens": 7},
        )


class FakeImageBackend:
    name = "fake-image"
    supports_reference_image = True
    last_prompt: str | None = None

    def generate_image(
        self,
        request: GenerationRequest,
        image_prompt: str,
        reference_image: bytes | None = None,
    ) -> ImageResult:
        self.last_prompt = image_prompt
        return ImageResult(path="/tmp/fake-ad.png", usage={"total_tokens": 3})


class FakeProductAnalyzer:
    name = "fake-analyzer"

    def analyze(
        self,
        request: GenerationRequest,
        reference_image: bytes | None = None,
    ) -> ProductAnalysis:
        return ProductAnalysis(
            label="fake",
            product_context=request.product_name,
            ad_goal="new ad",
            visual_strategy="minimal",
            photo_strategy="no reference",
            copy_focus="taste",
            rendering_strategy="overlay",
            analyzer_backend=self.name,
            detected_product_name="말차 푸딩",
            dominant_colors=["녹색", "크림색"],
            mood_keywords=["차분한", "프리미엄"],
            selling_points=["선물용", "진한 말차맛"],
            quality_notes=["배경 단순화 필요"],
            recommended_background="밝은 그린톤 카페 테이블",
            preservation_notes=["푸딩 컵 실루엣 보존"],
        )


class FakeMarketingContextRetriever:
    name = "fake-retriever"
    seen_product_analysis: ProductAnalysis | None = None

    def retrieve(
        self,
        request: GenerationRequest,
        product_analysis: ProductAnalysis,
    ) -> MarketingContext:
        self.seen_product_analysis = product_analysis
        return MarketingContext(
            retriever_backend=self.name,
            guide_categories=["cafe", "prohibited_claims"],
            copy_guidelines=["방문 동기를 먼저 제시한다."],
            prohibited_claims=["근거 없는 과장 표현을 쓰지 않는다."],
            source_doc_ids=["fake-cafe", "fake-claims"],
            retrieved_docs_count=2,
        )


def test_workflow_log_persists_completed_steps_before_write_log(tmp_path: Path) -> None:
    log_path = tmp_path / "generations.jsonl"
    deps = GenerationWorkflowDependencies(
        template_scorer=FakeTemplateScorer(),
        copy_backend=FakeCopyBackend(),
        image_backend=FakeImageBackend(),
        product_analyzer=FakeProductAnalyzer(),
        log_path=log_path,
    )

    output = run_generation_workflow(request_payload(), deps)
    log_record = json.loads(log_path.read_text(encoding="utf-8"))

    assert "workflow_trace" in log_record
    assert [entry["step"] for entry in log_record["workflow_trace"]] == [
        "rank_templates",
        "decode_reference",
        "analyze_product",
        "retrieve_marketing_context",
        "build_image_prompt",
        "generate_copy",
        "generate_image",
    ]
    assert output.trace[-1].step == "write_log"
    assert output.trace[-1].elapsed_ms > 0
    assert log_record["copy_backend"] == "fake-copy"
    assert log_record["image_backend"] == "fake-image"
    assert log_record["product_analysis_backend"] == "fake-analyzer"
    assert log_record["marketing_context_backend"] == "keyword"
    assert log_record["marketing_context_retrieved_docs_count"] >= 1
    assert log_record["used_reference"] is False


def test_workflow_uses_injected_logger_factory(tmp_path: Path) -> None:
    log_path = tmp_path / "custom-generations.jsonl"
    captured: dict[str, object] = {}

    class CapturingLogger:
        def __init__(self, path: str | Path) -> None:
            captured["path"] = path

        def write(self, record: dict[str, object]) -> None:
            captured["record"] = record

    def logger_factory(path: str | Path) -> CapturingLogger:
        captured["factory_path"] = path
        return CapturingLogger(path)

    deps = GenerationWorkflowDependencies(
        template_scorer=FakeTemplateScorer(),
        copy_backend=FakeCopyBackend(),
        image_backend=FakeImageBackend(),
        product_analyzer=FakeProductAnalyzer(),
        log_path=log_path,
        logger_factory=logger_factory,
    )

    output = run_generation_workflow(request_payload(), deps)

    assert captured["factory_path"] == log_path
    assert captured["path"] == log_path
    assert captured["record"]["copy_backend"] == "fake-copy"
    assert output.trace[-1].step == "write_log"
    assert not log_path.exists()


def test_workflow_feeds_product_analysis_into_image_prompt_and_trace(
    tmp_path: Path,
) -> None:
    image_backend = FakeImageBackend()
    deps = GenerationWorkflowDependencies(
        template_scorer=FakeTemplateScorer(),
        copy_backend=FakeCopyBackend(),
        image_backend=image_backend,
        product_analyzer=FakeProductAnalyzer(),
        log_path=tmp_path / "generations.jsonl",
    )

    output = run_generation_workflow(request_payload(), deps)
    build_prompt_trace = next(entry for entry in output.trace if entry.step == "build_image_prompt")

    assert output.response.product_analysis.selling_points == ["선물용", "진한 말차맛"]
    assert image_backend.last_prompt is not None
    assert "제품 분석 요약" in image_backend.last_prompt
    assert "감지 상품: 말차 푸딩" in image_backend.last_prompt
    assert "광고 포인트: 선물용, 진한 말차맛" in image_backend.last_prompt
    assert "추천 배경: 밝은 그린톤 카페 테이블" in image_backend.last_prompt
    assert build_prompt_trace.metadata["product_analysis_backend"] == "fake-analyzer"
    assert build_prompt_trace.metadata["has_selling_points"] is True
    assert build_prompt_trace.metadata["selling_points_count"] == 2
    assert "selling_points" not in build_prompt_trace.metadata


def test_workflow_feeds_marketing_context_into_copy_backend_and_trace(
    tmp_path: Path,
) -> None:
    copy_backend = FakeCopyBackend()
    marketing_context_retriever = FakeMarketingContextRetriever()
    deps = GenerationWorkflowDependencies(
        template_scorer=FakeTemplateScorer(),
        copy_backend=copy_backend,
        image_backend=FakeImageBackend(),
        product_analyzer=FakeProductAnalyzer(),
        marketing_context_retriever=marketing_context_retriever,
        log_path=tmp_path / "generations.jsonl",
    )

    output = run_generation_workflow(request_payload(), deps)
    retrieval_trace = next(
        entry for entry in output.trace if entry.step == "retrieve_marketing_context"
    )

    assert marketing_context_retriever.seen_product_analysis is not None
    assert copy_backend.last_product_analysis is output.response.product_analysis
    assert copy_backend.last_marketing_context is output.response.marketing_context
    assert output.response.marketing_context.retriever_backend == "fake-retriever"
    assert retrieval_trace.metadata == {
        "marketing_context_backend": "fake-retriever",
        "retrieved_docs_count": 2,
        "guide_categories": ["cafe", "prohibited_claims"],
    }
    assert "copy_guidelines" not in retrieval_trace.metadata
    assert "prohibited_claims" not in retrieval_trace.metadata


def test_workflow_emits_openinference_spans(tmp_path: Path) -> None:
    tracer = InMemoryWorkflowTracer()
    deps = GenerationWorkflowDependencies(
        template_scorer=FakeTemplateScorer(),
        copy_backend=FakeCopyBackend(),
        image_backend=FakeImageBackend(),
        product_analyzer=FakeProductAnalyzer(),
        log_path=tmp_path / "generations.jsonl",
        workflow_tracer=tracer,
    )

    run_generation_workflow(request_payload(), deps)

    records = tracer.records()
    assert [record.name for record in records] == [
        "generation_workflow",
        "rank_templates",
        "decode_reference",
        "analyze_product",
        "retrieve_marketing_context",
        "build_image_prompt",
        "generate_copy",
        "generate_image",
        "write_log",
    ]
    assert [record.kind for record in records] == [
        "AGENT",
        "RERANKER",
        "TOOL",
        "LLM",
        "RETRIEVER",
        "PROMPT",
        "LLM",
        "TOOL",
        "TOOL",
    ]
    assert [record.attributes["openinference.span.kind"] for record in records] == [
        "AGENT",
        "RERANKER",
        "TOOL",
        "LLM",
        "RETRIEVER",
        "PROMPT",
        "LLM",
        "TOOL",
        "TOOL",
    ]
    assert records[6].attributes["copy_backend"] == "fake-copy"
    assert records[7].attributes["image_backend"] == "fake-image"
    assert records[-1].attributes["has_log_path"] is True
    assert len(records[-1].attributes["log_path_sha256"]) == 64


def test_workflow_trace_and_log_use_privacy_allowlist(tmp_path: Path) -> None:
    tracer = InMemoryWorkflowTracer()
    log_path = tmp_path / "generations.jsonl"
    deps = GenerationWorkflowDependencies(
        template_scorer=FakeTemplateScorer(),
        copy_backend=FakeCopyBackend(),
        image_backend=FakeImageBackend(),
        product_analyzer=FakeProductAnalyzer(),
        log_path=log_path,
        workflow_tracer=tracer,
    )

    output = run_generation_workflow(sensitive_request_payload(), deps)
    log_record = json.loads(log_path.read_text(encoding="utf-8"))
    persistent_payload = {
        "workflow_trace": [entry.metadata for entry in output.trace],
        "span_attributes": [record.attributes for record in tracer.records()],
        "log_record": log_record,
    }
    serialized = json.dumps(persistent_payload, ensure_ascii=False)

    for raw_value in [
        "비공개 말차 푸딩",
        "VIP 고객에게만 보일 문구",
        "비공개 할인 강조",
        "secret-reference.png",
        "/tmp/fake-ad.png",
        "헤드라인",
        "본문",
    ]:
        assert raw_value not in serialized
    assert '"reference_image_name":' not in serialized
    assert '"image_path":' not in serialized
    assert "prompt_summary" not in serialized
    assert log_record["has_reference_image_name"] is True
    assert len(log_record["reference_image_name_sha256"]) == 64
    assert log_record["has_image_path"] is True
    assert len(log_record["image_path_sha256"]) == 64
