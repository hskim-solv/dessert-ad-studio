from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path
from typing import Any


DEFAULT_STORYBOARD_OUTPUT = Path("docs/evidence/demo-video-storyboard.md")
DEFAULT_SUMMARY_OUTPUT = Path("docs/evidence/demo-video-storyboard-summary.json")


@dataclass(frozen=True)
class StoryboardShot:
    order: int
    title: str
    duration_seconds: int
    visual: str
    narration: str
    evidence: tuple[str, ...]


def build_demo_video_storyboard_summary(*, evidence_date: str) -> dict[str, Any]:
    shots = _storyboard_shots()
    referenced_artifacts = _referenced_artifacts(shots)
    missing = [artifact for artifact in referenced_artifacts if not Path(artifact).exists()]
    passed = not missing and len(shots) >= 7
    return {
        "demo_video_storyboard": "passed" if passed else "failed",
        "scope": "offline_reviewer_demo_video_plan_no_paid_api_call",
        "evidence_date": evidence_date,
        "shot_count": len(shots),
        "estimated_duration_seconds": sum(shot.duration_seconds for shot in shots),
        "actual_video_file_committed": False,
        "provider_quality_claimed": False,
        "referenced_artifacts": referenced_artifacts,
        "missing_artifacts": missing,
        "coverage": {
            "agentic_rag_control_plane": _contains_artifact(
                referenced_artifacts, "agentic-rag-graph.md"
            ),
            "streaming_and_hitl": _contains_artifact(
                referenced_artifacts, "agentic-rag-streaming.md"
            )
            and _contains_artifact(referenced_artifacts, "agentic-rag-approval.md"),
            "eval_report": _contains_artifact(referenced_artifacts, "agentic-rag-eval-report.md"),
            "provider_quality_failure_disclosed": _contains_artifact(
                referenced_artifacts, "openai-image-edit-preservation.md"
            ),
        },
        "privacy_boundary": {
            "raw_customer_data_committed": False,
            "raw_prompt_committed": False,
            "raw_model_response_committed": False,
            "paid_api_call_count": 0,
        },
    }


def render_demo_video_storyboard(summary: dict[str, Any]) -> str:
    shot_sections = "\n\n".join(_render_shot(shot) for shot in _storyboard_shots())
    artifacts = "\n".join(f"- `{artifact}`" for artifact in summary["referenced_artifacts"])
    return f"""# Demo Video Storyboard

Date: {summary["evidence_date"]}

This is the reproducible recording plan for a portfolio demo video. It shows
Dessert Ad Studio as a Production-grade Agentic RAG System for small-business
ad generation while keeping proven and pending scope explicit.

## Recording Boundary

- Actual video file committed: `{_bool_text(summary["actual_video_file_committed"])}`
- Paid API calls required: `0`
- Raw customer data committed: `{_bool_text(summary["privacy_boundary"]["raw_customer_data_committed"])}`
- Do not claim provider-quality image editing; the paid provider-quality gate
  remains failed and documented.

## Shot List

{shot_sections}

## Referenced Artifacts

{artifacts}

## Reproduce

```bash
.venv/bin/python scripts/build_demo_video_storyboard.py \\
  --date {summary["evidence_date"]} \\
  --storyboard-output docs/evidence/demo-video-storyboard.md \\
  --summary-output docs/evidence/demo-video-storyboard-summary.json
```

## Remaining Work

Record and commit or link the final demo video only after this storyboard is
used to capture the reviewer flow. Keep the provider-quality image-edit failure
visible in the narration and avoid presenting paid OpenAI image editing as a
proven capability.
"""


def _storyboard_shots() -> tuple[StoryboardShot, ...]:
    return (
        StoryboardShot(
            order=1,
            title="Positioning and architecture",
            duration_seconds=20,
            visual="Open README and architecture diagram.",
            narration=(
                "Dessert Ad Studio is positioned as an Agentic RAG control plane "
                "for small-business ad generation, not as a custom image model."
            ),
            evidence=(
                "README.md",
                "docs/evidence/assets/architecture.svg",
                "docs/reference/dessert-ad-studio-final-outcome.md",
            ),
        ),
        StoryboardShot(
            order=2,
            title="Reviewer-facing product flow",
            duration_seconds=25,
            visual="Show Streamlit input and generated result screenshots.",
            narration=(
                "A reviewer can inspect the request, product image, generated "
                "banner, revised Korean copy, and download action."
            ),
            evidence=(
                "docs/evidence/streamlit-reviewer-flow.md",
                "docs/evidence/assets/streamlit-reviewer-input.png",
                "docs/evidence/assets/streamlit-reviewer-result.png",
            ),
        ),
        StoryboardShot(
            order=3,
            title="Representative outputs",
            duration_seconds=20,
            visual="Show the committed deterministic demo gallery.",
            narration=(
                "The demo gallery proves Korean overlay rendering and repeatable "
                "small-business ad scenarios without external API keys."
            ),
            evidence=(
                "docs/evidence/demo-gallery.md",
                "docs/evidence/assets/demo-gallery/demo-01.png",
                "docs/evidence/assets/demo-gallery/demo-02.png",
                "docs/evidence/assets/demo-gallery/demo-03.png",
            ),
        ),
        StoryboardShot(
            order=4,
            title="Agentic RAG control plane",
            duration_seconds=22,
            visual="Show graph, streaming, checkpoint, and replay evidence.",
            narration=(
                "LangGraph typed state, conditional HITL routing, local tools, "
                "citations, checkpointing, retry/reflection, and run replay are "
                "recorded as reproducible first gates."
            ),
            evidence=(
                "docs/evidence/agentic-rag-graph.md",
                "docs/evidence/agentic-rag-streaming.md",
                "docs/evidence/agentic-rag-sqlite-checkpoint.md",
                "docs/evidence/agentic-rag-approval.md",
            ),
        ),
        StoryboardShot(
            order=5,
            title="Tool suite and retrieval quality",
            duration_seconds=22,
            visual="Show tool-suite, RAG baseline, chunking, and pgvector evidence.",
            narration=(
                "The system uses document retrieval, local web-search snapshot, "
                "allowlisted SQL, internal API policy preview, FastMCP smoke, "
                "chunking comparison, and pgvector hybrid retrieval evidence."
            ),
            evidence=(
                "docs/evidence/agentic-rag-tools.md",
                "docs/evidence/rag-baseline.md",
                "docs/evidence/rag-chunking-comparison.md",
                "docs/evidence/pgvector-retrieval.md",
            ),
        ),
        StoryboardShot(
            order=6,
            title="Evaluation, guardrails, and observability",
            duration_seconds=26,
            visual="Show eval report and Phoenix trace screenshots.",
            narration=(
                "The reviewer sees golden eval, Ragas-compatible metrics, "
                "promptfoo, prompt-injection blocking, tool budgets, raw-input "
                "absence, run metrics, and Phoenix/OpenInference trace evidence."
            ),
            evidence=(
                "docs/evidence/agentic-rag-eval-report.md",
                "docs/evidence/agentic-rag-run-metrics.md",
                "docs/evidence/agentic-rag-trace.md",
                "docs/evidence/agentops-phoenix.md",
                "docs/evidence/assets/phoenix-workflow-trace.png",
                "docs/evidence/assets/phoenix-trace-detail.png",
            ),
        ),
        StoryboardShot(
            order=7,
            title="Deployability and reliability",
            duration_seconds=25,
            visual="Show Docker/Kubernetes and async reliability evidence.",
            narration=(
                "Docker, GitHub Actions, Kubernetes render/live-kind smokes, "
                "async worker outage/restore, and explicit retry/timeout/cancel "
                "boundaries are documented."
            ),
            evidence=(
                "docs/evidence/k8s-deployment.md",
                "docs/evidence/async-reliability-matrix.md",
                "docs/evidence/generation-jobs.md",
            ),
        ),
        StoryboardShot(
            order=8,
            title="Honest pending scope",
            duration_seconds=20,
            visual="Show provider-quality failure and final outcome pending rows.",
            narration=(
                "Provider-quality OpenAI image editing is not claimed as proven; "
                "live web search, production SQL, production MCP auth, cloud "
                "deployment, and the final recorded video remain pending."
            ),
            evidence=(
                "docs/evidence/openai-image-edit-preservation.md",
                "docs/evidence/provider-gate-postmortem.md",
                "docs/reference/dessert-ad-studio-final-outcome.md",
            ),
        ),
    )


def _referenced_artifacts(shots: tuple[StoryboardShot, ...]) -> list[str]:
    artifacts: list[str] = []
    for shot in shots:
        for artifact in shot.evidence:
            if artifact not in artifacts:
                artifacts.append(artifact)
    return artifacts


def _render_shot(shot: StoryboardShot) -> str:
    evidence = "\n".join(f"  - `{artifact}`" for artifact in shot.evidence)
    return f"""### {shot.order}. {shot.title}

- Duration: `{shot.duration_seconds}s`
- Visual: {shot.visual}
- Narration: {shot.narration}
- Evidence:
{evidence}"""


def _contains_artifact(artifacts: list[str], suffix: str) -> bool:
    return any(artifact.endswith(suffix) for artifact in artifacts)


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a reviewer-facing demo video storyboard from committed evidence."
    )
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--storyboard-output", type=Path, default=DEFAULT_STORYBOARD_OUTPUT)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY_OUTPUT)
    args = parser.parse_args()

    summary = build_demo_video_storyboard_summary(evidence_date=args.date)
    storyboard = render_demo_video_storyboard(summary)
    summary_payload = json.dumps(summary, ensure_ascii=False, indent=2)

    args.storyboard_output.parent.mkdir(parents=True, exist_ok=True)
    args.summary_output.parent.mkdir(parents=True, exist_ok=True)
    args.storyboard_output.write_text(storyboard, encoding="utf-8")
    args.summary_output.write_text(summary_payload + "\n", encoding="utf-8")
    print(summary_payload)
    return 0 if summary["demo_video_storyboard"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
