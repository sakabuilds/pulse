#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
command -v uv >/dev/null || { echo "uv is required: https://docs.astral.sh/uv/" >&2; exit 1; }
uv venv --python 3.11 .venv 2>/dev/null || true
uv pip install --python .venv/bin/python -r memory-mcp/requirements.txt pytest
echo "Setup complete. Run: .venv/bin/pytest -q memory-mcp/test_server.py"
