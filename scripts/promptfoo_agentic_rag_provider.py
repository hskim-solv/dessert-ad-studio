from __future__ import annotations

import json

from agentic_rag_eval_guardrail import build_agentic_rag_eval_guardrail_summary


def main() -> int:
    summary = build_agentic_rag_eval_guardrail_summary(evidence_date="2026-06-17")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
