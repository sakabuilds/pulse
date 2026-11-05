# Phase 0 spike record

Date: 2026-11-05

## Results

1. One agent answers in a Mattermost/Console room: **pass**, confirmed by the
   user after the local Console setup.
2. Same template in two rooms: **pending**.
3. Telegram or Discord bridge: **pending**; Mattermost is the first bridge.
4. Agent calls a trivial MCP tool with per-instance configuration: **pass for
   configuration**; the three Codex provider homes report `pulse-memory`
   enabled, with the live call smoke test still to be run from each room.
5. Script posts into a room: **pending**.
6. Agent/script posts into a different room: **pending**.

## Verified local facts

- Switch Console 0.40.1 is installed and running.
- The local Switch server and bundled Mattermost are running.
- The Switch agent controller is connected.
- The local Switch source and `examples/agent-templates/triage-pair.template.yaml`
  were read before writing the PULSE template.

The template language documents agents, rooms, bridges, providers, locations,
directories, and kickoffs; it does not document an MCP-server field in a
template. The supported Codex path is its per-session `CODEX_HOME/config.toml`
with an `mcp_servers.pulse-memory` stdio entry, configured by
`scripts/configure-switch-mcp.sh`.
