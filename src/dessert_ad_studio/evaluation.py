from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any

from dessert_ad_studio.schemas import CopyOption, GenerationRequest
from dessert_ad_studio.workflow import GenerationWorkflowOutput

REQUIRED_WORKFLOW_STEPS = (
    "rank_templates",
    "decode_reference",
    "analyze_product",
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


def _check(name: str, passed: bool, detail: str) -> EvalCheck:
    return EvalCheck(name=name, passed=passed, score=1.0 if passed else 0.0, detail=detail)


def _copy_text(option: CopyOption) -> str:
    return f"{option.headline} {option.body} {option.call_to_action}"


def _has_korean(value: str) -> bool:
    return _KOREAN_RE.search(value) is not None
