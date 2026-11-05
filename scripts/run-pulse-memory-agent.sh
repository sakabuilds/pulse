#!/usr/bin/env bash
set -euo pipefail

# Codex starts stdio MCP servers with the managed agent's working directory.
# Keep the audience decision here and repeat it in the Python server's checks;
# an unrecognised directory fails closed.
case "$PWD" in
  */pulse-community|*/pulse-community/*) audience=public ;;
  */pulse-team|*/pulse-team/*) audience=internal ;;
  */pulse-supervisor|*/pulse-supervisor/*) audience=private ;;
  *) echo "pulse-memory: refusing unknown agent working directory: $PWD" >&2; exit 1 ;;
esac

cd "/home/xprogrammmer/Documents/switch hack"
export PULSE_AUDIENCE="$audience"
export PULSE_DB="/home/xprogrammmer/Documents/switch hack/memory-mcp/pulse.sqlite3"
exec .venv/bin/python memory-mcp/server.py
