from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any

from dessert_ad_studio.schemas import CopyOption, GenerationRequest, MarketingContext
from dessert_ad_studio.workflow import GenerationWorkflowOutput

REQUIRED_WORKFLOW_STEPS = (
    "rank_templates",
    "decode_reference",
    "analyze_product",
    "retrieve_marketing_context",
    "build_image_prompt",
    "generate_copy",
    "generate_image",
    "write_log",
)
_KOREAN_RE = re.compile(r"[가-힣]")


@dataclass(frozen=True)
class EvalCheck:
    name: str
    passed: bool
    score: float
    detail: str


@dataclass(frozen=True)
class GenerationEvalResult:
    sample_label: str
    score: float
    passed: bool
    checks: list[EvalCheck]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvalSummary:
    sample_count: int
    average_score: float
    passed: bool
    threshold: float
    results: list[GenerationEvalResult]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MarketingContextEvalResult:
    sample_label: str
    category_hit_rate: float
    category_precision: float
    required_category_hit_rate: float
    passed: bool
    threshold: float
    expected_categories: list[str]
    retrieved_categories: list[str]
    matched_categories: list[str]
    missing_categories: list[str]
    unexpected_categories: list[str]
    required_categories: list[str]
    missing_required_categories: list[str]
    retrieved_docs_count: int
    source_doc_ids: list[str]
    checks: list[EvalCheck]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MarketingContextEvalSummary:
    sample_count: int
    average_category_hit_rate: float
    average_category_precision: float
    required_category_hit_rate: float
    passed: bool
    threshold: float
    results: list[MarketingContextEvalResult]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_generation_output(
    sample_label: str,
    request: GenerationRequest,
    output: GenerationWorkflowOutput,
    threshold: float = 0.8,
) -> GenerationEvalResult:
    response = output.response
    checks = [
        _check(
            "copy.option_count",
            len(response.copy_options) >= 3,
            f"expected at least 3 copy options, got {len(response.copy_options)}",
        ),
        _check(
            "copy.korean_text",
            bool(response.copy_options)
            and all(_has_korean(_copy_text(option)) for option in response.copy_options),
            "all copy options contain Korean text",
        ),
        _check(
            "copy.product_name",
            any(request.product_name in _copy_text(option) for option in response.copy_options),
            "product name appears in generated copy",
        ),
        _check("image.path", bool(response.image_path.strip()), "image path is populated"),
        _check(
            "product_analysis.present",
            response.product_analysis is not None
            and bool(response.product_analysis.analyzer_backend.strip()),
            "product analysis is present",
        ),
        _check(
            "workflow.required_steps",
            tuple(entry.step for entry in output.trace) == REQUIRED_WORKFLOW_STEPS,
            "workflow trace has required ordered steps",
        ),
        _check(
            "workflow.elapsed_ms",
            response.elapsed_ms >= 0 and all(entry.elapsed_ms >= 0 for entry in output.trace),
            "response and step elapsed times are non-negative",
        ),
    ]
    score = sum(check.score for check in checks) / len(checks)
    return GenerationEvalResult(
        sample_label=sample_label,
        score=score,
        passed=score >= threshold and all(check.passed for check in checks),
        checks=checks,
    )


def summarize_eval_results(
    results: list[GenerationEvalResult],
    threshold: float = 0.8,
) -> EvalSummary:
    sample_count = len(results)
    average_score = (
        sum(result.score for result in results) / sample_count if sample_count else 0.0
    )
    return EvalSummary(
        sample_count=sample_count,
        average_score=average_score,
        passed=sample_count > 0
        and average_score >= threshold
        and all(result.passed for result in results),
        threshold=threshold,
        results=results,
    )


def evaluate_marketing_context_retrieval(
    sample_label: str,
    context: MarketingContext,
    expected_categories: tuple[str, ...],
    required_categories: tuple[str, ...] = ("prohibited_claims",),
    threshold: float = 0.8,
) -> MarketingContextEvalResult:
    expected = _unique_ordered(expected_categories)
    required = _unique_ordered(required_categories)
    retrieved_categories = _unique_ordered(context.guide_categories)
    actual_categories = set(retrieved_categories)
    matched_categories = [category for category in expected if category in actual_categories]
    missing_categories = [category for category in expected if category not in actual_categories]
    unexpected_categories = [
        category for category in retrieved_categories if category not in set(expected)
    ]
    missing_required_categories = [
        category for category in required if category not in actual_categories
    ]
    category_hit_rate = len(matched_categories) / len(expected) if expected else 1.0
    category_precision = (
        len(matched_categories) / len(retrieved_categories) if retrieved_categories else 0.0
    )
    required_category_hit_rate = (
        (len(required) - len(missing_required_categories)) / len(required)
        if required
        else 1.0
    )
    checks = [
        _check(
            "retrieval.docs_count",
            context.retrieved_docs_count > 0,
            f"retrieved {context.retrieved_docs_count} guide docs",
        ),
        _check(
            "retrieval.category_hit_rate",
            category_hit_rate >= threshold,
            f"matched {len(matched_categories)} of {len(expected)} expected categories",
        ),
        _check(
            "retrieval.required_categories",
            required_category_hit_rate == 1.0,
            f"missing required categories: {', '.join(missing_required_categories) or 'none'}",
        ),
        _check(
            "retrieval.source_doc_ids",
            len(context.source_doc_ids) == context.retrieved_docs_count
            and len(set(context.source_doc_ids)) == len(context.source_doc_ids),
            "source doc IDs are present and unique",
        ),
    ]
    return MarketingContextEvalResult(
        sample_label=sample_label,
        category_hit_rate=category_hit_rate,
        category_precision=category_precision,
        required_category_hit_rate=required_category_hit_rate,
        passed=all(check.passed for check in checks),
        threshold=threshold,
        expected_categories=expected,
        retrieved_categories=retrieved_categories,
        matched_categories=matched_categories,
        missing_categories=missing_categories,
        unexpected_categories=unexpected_categories,
        required_categories=required,
        missing_required_categories=missing_required_categories,
        retrieved_docs_count=context.retrieved_docs_count,
        source_doc_ids=list(context.source_doc_ids),
        checks=checks,
    )


def summarize_marketing_context_eval_results(
    results: list[MarketingContextEvalResult],
    threshold: float = 0.8,
) -> MarketingContextEvalSummary:
    sample_count = len(results)
    average_category_hit_rate = (
        sum(result.category_hit_rate for result in results) / sample_count
        if sample_count
        else 0.0
    )
    average_category_precision = (
        sum(result.category_precision for result in results) / sample_count
        if sample_count
        else 0.0
    )
    required_category_hit_rate = (
        sum(result.required_category_hit_rate for result in results) / sample_count
        if sample_count
        else 0.0
    )
    return MarketingContextEvalSummary(
        sample_count=sample_count,
        average_category_hit_rate=average_category_hit_rate,
        average_category_precision=average_category_precision,
        required_category_hit_rate=required_category_hit_rate,
        passed=sample_count > 0
        and average_category_hit_rate >= threshold
        and required_category_hit_rate == 1.0
        and all(result.passed for result in results),
        threshold=threshold,
        results=results,
    )


def _check(name: str, passed: bool, detail: str) -> EvalCheck:
    return EvalCheck(name=name, passed=passed, score=1.0 if passed else 0.0, detail=detail)


def _copy_text(option: CopyOption) -> str:
    return f"{option.headline} {option.body} {option.call_to_action}"


def _has_korean(value: str) -> bool:
    return _KOREAN_RE.search(value) is not None


def _unique_ordered(values) -> list[str]:
    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            unique_values.append(value)
    return unique_values
