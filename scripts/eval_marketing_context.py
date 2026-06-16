from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dessert_ad_studio.evaluation import (  # noqa: E402
    evaluate_marketing_context_retrieval,
    summarize_marketing_context_eval_results,
)
from dessert_ad_studio.marketing_context import KeywordMarketingContextRetriever  # noqa: E402
from dessert_ad_studio.marketing_context_eval_cases import (  # noqa: E402
    MARKETING_CONTEXT_EVAL_CASES,
)
from dessert_ad_studio.product_analysis import MockProductAnalyzer  # noqa: E402


def run_eval(threshold: float):
    retriever = KeywordMarketingContextRetriever()
    analyzer = MockProductAnalyzer()
    results = []
    for case in MARKETING_CONTEXT_EVAL_CASES:
        analysis = analyzer.analyze(case.request)
        context = retriever.retrieve(case.request, analysis)
        results.append(
            evaluate_marketing_context_retrieval(
                sample_label=case.label,
                context=context,
                expected_categories=case.expected_categories,
                required_categories=("prohibited_claims",),
                threshold=threshold,
            )
        )
    return summarize_marketing_context_eval_results(results, threshold=threshold)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate deterministic keyword marketing-context retrieval."
    )
    parser.add_argument("--threshold", type=float, default=0.8)
    parser.add_argument("--output", help="Optional JSON output path.")
    args = parser.parse_args()

    summary = run_eval(threshold=args.threshold)
    payload = json.dumps(summary.to_dict(), ensure_ascii=False, indent=2)
    print(payload)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload + "\n", encoding="utf-8")
    return 0 if summary.passed else 1


if __name__ == "__main__":
    sys.exit(main())
