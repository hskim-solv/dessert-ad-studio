from __future__ import annotations

import argparse
from datetime import date
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUMMARY_OUTPUT = Path("docs/evidence/agentic-rag-promptfoo-package-summary.json")
DEFAULT_RESULTS_OUTPUT = Path("docs/evidence/agentic-rag-promptfoo-results.json")
PROMPTFOO_VERSION = "0.121.17"


def build_promptfoo_package_smoke_summary(
    *,
    evidence_date: str,
    results_output: Path,
    timeout_seconds: float,
    dry_run_command: bool,
) -> dict[str, Any]:
    command = _promptfoo_command(results_output)
    summary: dict[str, Any] = {
        "agentic_rag_promptfoo_package_smoke": "passed",
        "scope": "local_promptfoo_package_execution_no_paid_api_call",
        "evidence_date": evidence_date,
        "promptfoo_package": "promptfoo",
        "promptfoo_version": PROMPTFOO_VERSION,
        "config": "evals/promptfoo/agentic-rag.yaml",
        "results_output": str(results_output),
        "timeout_seconds": timeout_seconds,
        "command": _display_command(command),
        "telemetry_disabled": True,
        "cache_disabled": True,
        "progress_bar_disabled": True,
        "table_disabled": True,
        "paid_api_call_count": 0,
        "raw_inputs_committed": False,
    }
    if dry_run_command:
        summary["execution_mode"] = "dry_run_command"
        return summary

    completed = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        check=False,
        env=_promptfoo_env(),
        text=True,
        timeout=timeout_seconds,
    )
    summary["execution_mode"] = "package_eval"
    summary["returncode"] = completed.returncode
    summary["stdout_tail"] = _tail_without_raw_payload(completed.stdout)
    summary["stderr_tail"] = _tail_without_raw_payload(completed.stderr)
    summary["results_file_created"] = results_output.exists()
    summary["results_file_size_bytes"] = (
        results_output.stat().st_size if results_output.exists() else 0
    )
    if results_output.exists():
        summary["promptfoo_results"] = _promptfoo_results_summary(results_output)
    summary["promptfoo_eval_passed"] = completed.returncode == 0 and results_output.exists()
    if completed.returncode != 0:
        raise SystemExit(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def _promptfoo_command(results_output: Path) -> list[str]:
    executable = ROOT / "node_modules" / ".bin" / "promptfoo"
    command_head = [str(executable)] if executable.exists() else ["npx", "--yes", "promptfoo"]
    return [
        *command_head,
        "eval",
        "-c",
        "evals/promptfoo/agentic-rag.yaml",
        "--no-cache",
        "--no-progress-bar",
        "--no-table",
        "-o",
        str(results_output),
    ]


def _display_command(command: list[str]) -> list[str]:
    display: list[str] = []
    for part in command:
        try:
            display.append(str(Path(part).relative_to(ROOT)))
        except ValueError:
            display.append(part)
    return display


def _promptfoo_results_summary(results_output: Path) -> dict[str, Any]:
    payload = json.loads(results_output.read_text(encoding="utf-8"))
    stats = payload.get("results", {}).get("stats", {})
    prompts = payload.get("results", {}).get("prompts", [])
    metrics = prompts[0].get("metrics", {}) if prompts else {}
    return {
        "successes": stats.get("successes", 0),
        "failures": stats.get("failures", 0),
        "errors": stats.get("errors", 0),
        "assert_pass_count": metrics.get("assertPassCount", 0),
        "assert_fail_count": metrics.get("assertFailCount", 0),
        "duration_ms": stats.get("durationMs", 0),
        "token_usage_total": stats.get("tokenUsage", {}).get("total", 0),
        "cost": metrics.get("cost", 0),
    }


def _promptfoo_env() -> dict[str, str]:
    keep_keys = ("HOME", "PATH", "TMPDIR", "LANG", "LC_ALL", "PYTHONPATH")
    env = {key: value for key in keep_keys if (value := os.environ.get(key))}
    env["PROMPTFOO_DISABLE_TELEMETRY"] = "1"
    env["IS_TESTING"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    return env


def _tail_without_raw_payload(output: str) -> list[str]:
    return [line for line in output.splitlines()[-20:] if not line.strip().startswith("{")]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a bounded local promptfoo package smoke for Agentic RAG.",
        allow_abbrev=False,
    )
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY_OUTPUT)
    parser.add_argument("--results-output", type=Path, default=DEFAULT_RESULTS_OUTPUT)
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument("--dry-run-command", action="store_true")
    args = parser.parse_args()

    summary = build_promptfoo_package_smoke_summary(
        evidence_date=args.date,
        results_output=args.results_output,
        timeout_seconds=args.timeout_seconds,
        dry_run_command=args.dry_run_command,
    )
    payload = json.dumps(summary, ensure_ascii=False, indent=2)
    print(payload)
    args.summary_output.parent.mkdir(parents=True, exist_ok=True)
    args.summary_output.write_text(payload + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
