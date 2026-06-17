#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then
  exec "${ROOT_DIR}/.venv/bin/python" "${SCRIPT_DIR}/promptfoo_agentic_rag_provider.py"
fi

if command -v python3 >/dev/null 2>&1; then
  exec python3 "${SCRIPT_DIR}/promptfoo_agentic_rag_provider.py"
fi

exec python "${SCRIPT_DIR}/promptfoo_agentic_rag_provider.py"
