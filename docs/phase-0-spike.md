# Phase 0 spike record

Date: 2026-11-05

## Results

1. One agent answers in a Mattermost/Console room: **pass**, confirmed by the
   user after the local Console setup.
2. Same template in two rooms: **pass**, three managed Pulse identities are
   provisioned in Mattermost with audience-scoped MCP instances.
3. Telegram bridge: **pass manually**; the connected Pulse bot responds in a
   Telegram chat. Automated Telegram ingestion worker is implemented and
   locally tested, but needs a deployed bot-token runtime for live polling.
4. Agent calls a trivial MCP tool with per-instance configuration: **pass**;
   all three launchers expose 8 memory tools and `brief` returns the expected
   public, internal, or private audience.
5. Script posts into a room: **hook implemented**, publisher callback tested;
   live Switch publisher URL remains deployment-specific.
6. Agent/script posts into a different room: **hook implemented**, approved
   replies enter the outbox and the Switch provisioner receives deterministic
   room assignments; live multi-room delivery remains deployment-specific.

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
