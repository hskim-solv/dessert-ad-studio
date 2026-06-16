from pathlib import Path

from dessert_ad_studio.backends.mock import MockAdBackend
from dessert_ad_studio.evaluation import (
    REQUIRED_WORKFLOW_STEPS,
    evaluate_generation_output,
    summarize_eval_results,
)
from dessert_ad_studio.product_analysis import MockProductAnalyzer
from dessert_ad_studio.schemas import GenerationRequest
from dessert_ad_studio.triton import LocalTemplateScorer
from dessert_ad_studio.workflow import GenerationWorkflowDependencies, run_generation_workflow


def sample_request() -> GenerationRequest:
    return GenerationRequest(
        campaign_purpose="new_menu",
        product_name="말차 푸딩",
        tone="clean",
        template_hint="minimal_premium",
        price_text="5,500원",
        user_constraints="깔끔한 프리미엄 느낌",
    )


def mock_output(tmp_path: Path):
    backend = MockAdBackend(output_dir=tmp_path)
    return run_generation_workflow(
        sample_request(),
        GenerationWorkflowDependencies(
            template_scorer=LocalTemplateScorer(),
            copy_backend=backend,
            image_backend=backend,
            product_analyzer=MockProductAnalyzer(),
            log_path=tmp_path / "generations.jsonl",
        ),
    )


def test_evaluate_generation_output_scores_valid_mock_generation(tmp_path: Path) -> None:
    result = evaluate_generation_output("sample", sample_request(), mock_output(tmp_path))

    assert result.passed is True
    assert result.score >= 0.8
    assert all(check.passed for check in result.checks)
    assert result.to_dict()["sample_label"] == "sample"


def test_evaluate_generation_output_reports_missing_workflow_step(tmp_path: Path) -> None:
    output = mock_output(tmp_path)
    output.trace.pop()

    result = evaluate_generation_output("sample", sample_request(), output)

    assert result.passed is False
    assert any(check.name == "workflow.required_steps" and not check.passed for check in result.checks)
    assert REQUIRED_WORKFLOW_STEPS == (
        "rank_templates",
        "decode_reference",
        "analyze_product",
        "retrieve_marketing_context",
        "build_image_prompt",
        "generate_copy",
        "generate_image",
        "write_log",
    )


def test_summarize_eval_results_aggregates_scores(tmp_path: Path) -> None:
    result = evaluate_generation_output("sample", sample_request(), mock_output(tmp_path))
    summary = summarize_eval_results([result], threshold=0.8)

    assert summary.passed is True
    assert summary.sample_count == 1
    assert summary.average_score == result.score
    assert summary.to_dict()["results"][0]["sample_label"] == "sample"
