import json
from pathlib import Path

from dessert_ad_studio.backends.base import CopyResult, ImageResult
from dessert_ad_studio.backends.mock import MockAdBackend
from dessert_ad_studio.product_analysis import MockProductAnalyzer
from dessert_ad_studio.schemas import CopyOption, GenerationRequest, ProductAnalysis, TemplateRanking
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
        "build_image_prompt",
        "generate_copy",
        "generate_image",
        "write_log",
    ]
    assert output.trace[-1].metadata["log_path"].endswith("generations.jsonl")


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

    def generate_copy(self, request: GenerationRequest) -> CopyResult:
        return CopyResult(
            options=[
                CopyOption(headline="헤드라인", body="본문", call_to_action="방문하기"),
            ],
            usage={"total_tokens": 7},
        )


class FakeImageBackend:
    name = "fake-image"
    supports_reference_image = True

    def generate_image(
        self,
        request: GenerationRequest,
        image_prompt: str,
        reference_image: bytes | None = None,
    ) -> ImageResult:
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
        "build_image_prompt",
        "generate_copy",
        "generate_image",
    ]
    assert output.trace[-1].step == "write_log"
    assert output.trace[-1].elapsed_ms > 0
    assert log_record["copy_backend"] == "fake-copy"
    assert log_record["image_backend"] == "fake-image"
    assert log_record["product_analysis_backend"] == "fake-analyzer"
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
