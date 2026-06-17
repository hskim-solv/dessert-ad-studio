#!/usr/bin/env bash
set -euo pipefail

if [[ -x ".venv/bin/python" ]]; then
  exec .venv/bin/python scripts/promptfoo_agentic_rag_provider.py
fi

if command -v python3 >/dev/null 2>&1; then
  exec python3 scripts/promptfoo_agentic_rag_provider.py
fi

exec python scripts/promptfoo_agentic_rag_provider.py
