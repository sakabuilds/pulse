#!/usr/bin/env bash
set -euo pipefail

audience="${1:?usage: $0 public|internal|private}"
case "$audience" in
  public|internal|private) ;;
  *) echo "audience must be public, internal, or private" >&2; exit 2 ;;
esac

cd "$(dirname "$0")/.."
exec .venv/bin/python memory-mcp/server.py
