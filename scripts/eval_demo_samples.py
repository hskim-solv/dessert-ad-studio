from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from dessert_ad_studio.backends.mock import MockAdBackend
from dessert_ad_studio.demo_samples import DEMO_SAMPLES, DemoSample
from dessert_ad_studio.evaluation import evaluate_generation_output, summarize_eval_results
from dessert_ad_studio.product_analysis import MockProductAnalyzer
from dessert_ad_studio.schemas import GenerationRequest
from dessert_ad_studio.triton import LocalTemplateScorer
from dessert_ad_studio.workflow import GenerationWorkflowDependencies, run_generation_workflow


def request_from_sample(sample: DemoSample) -> GenerationRequest:
    return GenerationRequest(
        campaign_purpose=sample.campaign_purpose,
        product_name=sample.product_name,
        tone=sample.tone,
        template_hint=sample.template_hint,
        price_text=sample.price_text,
        user_constraints=sample.user_constraints,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run deterministic evals for demo samples.",
        allow_abbrev=False,
    )
    parser.add_argument("--threshold", type=float, default=0.8)
    parser.add_argument("--output-dir", default="outputs/eval")
    parser.add_argument("--log-path", default="logs/eval-generations.jsonl")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    log_path = Path(args.log_path)
    results = []

    for sample in DEMO_SAMPLES:
        backend = MockAdBackend(output_dir=output_dir)
        request = request_from_sample(sample)
        output = run_generation_workflow(
            request,
            GenerationWorkflowDependencies(
                template_scorer=LocalTemplateScorer(),
                copy_backend=backend,
                image_backend=backend,
                product_analyzer=MockProductAnalyzer(),
                log_path=log_path,
            ),
        )
        results.append(
            evaluate_generation_output(
                sample.label,
                request,
                output,
                threshold=args.threshold,
            )
        )

    summary = summarize_eval_results(results, threshold=args.threshold)
    payload = json.dumps(summary.to_dict(), ensure_ascii=False, indent=2)
    print(payload)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    return 0 if summary.passed else 1


if __name__ == "__main__":
    sys.exit(main())
