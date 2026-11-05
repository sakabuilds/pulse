#!/usr/bin/env bash
set -euo pipefail

root="/home/xprogrammmer/Documents/switch hack"
command_path="$root/scripts/run-pulse-memory-agent.sh"

mapfile -t configs < <(rg -l 'You are Pulse, the shared-memory teammate' "$HOME/.local/state/switch/sdk-sessions" -g 'config.toml' 2>/dev/null || true)
if [ "${#configs[@]}" -eq 0 ]; then
  echo "No live Pulse provider configs found. Start the three Switch agents first." >&2
  exit 1
fi

for config in "${configs[@]}"; do
  if rg -q '^\[mcp_servers\.pulse-memory\]' "$config"; then
    echo "already configured: $config"
    continue
  fi
  cat >>"$config" <<EOF

[mcp_servers.pulse-memory]
command = "$command_path"
startup_timeout_sec = 20
EOF
  echo "configured: $config"
done
