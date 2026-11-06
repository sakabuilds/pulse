# PULSE

PULSE is a team memory workflow for public communities, internal teams, and
supervisors. One agent appears in three Switch rooms, records signals in a
shared SQLite memory, and helps a supervisor brief the team or prepare an
approved public reply.

## Current status

Phase 0 is verified locally: Switch Console, the local Switch server,
Mattermost, and a Codex-backed agent are running; the agent has answered in
its private Switch chat. Phase 1 is implemented and tested. The three Pulse
agents and rooms have now been provisioned in the live local Switch workspace.
Per-instance MCP attachment, cross-room posting, and the GitHub watcher are
next.

## Repository layout

```text
agents/       Switch templates
memory-mcp/   SQLite memory MCP server and tests
scripts/      setup and deterministic demo scripts
switch/       local Switch source/docs reference clone
```

## Setup

Requirements: Python 3.11, `uv`, and a working Switch Console installation.

```bash
./scripts/setup.sh
cp .env.example .env
PYTHONPATH=memory-mcp .venv/bin/pytest -q memory-mcp/test_server.py
```

## Seed

```bash
.venv/bin/python scripts/seed.py
```

The seed is deterministic and creates 51 signals across community and team
contexts. The three recurring topics are `login-mobile`, `export-slow`, and
`pricing-confusing`.

To run one memory instance manually during local integration testing:

```bash
PULSE_AUDIENCE=public ./scripts/run-memory.sh public
```

## How Switch is used

Switch is central: it supplies the shared room history, agent identity,
addressing, triggers, and chat bridges. PULSE uses three rooms:

- `community`: public signals only; no unapproved public claims.
- `team`: public and internal signals; no private supervisor data.
- `supervisor`: all signals; drafts public replies and waits for approval.

The same `Pulse` template in `agents/pulse.template.yaml` is instantiated once
per Pulse identity, then that identity can be invited into rooms on any number
of connected messaging apps. The many-to-many routing is declared in
`config/pulse.assignments.yaml`: it is valid for Supervisor to be on Telegram,
Slack, and Mattermost at the same time, or for all three identities to share
every connected app. The memory server is a separate MCP process with an
audience setting per identity. Switch room messages trigger agent turns; the
GitHub watcher and scheduled digest will use the supervisor room as explicit
nudges.

Supervisor is private-only. On Telegram, Pulse presents a one-person group
(`user + Pulse bot`) as a private supervisor chat because Switch cannot attach
an agent to a direct bot DM. Community and Team are the only identities allowed
in shared channels.

Validate the routing plan with:

```bash
.venv/bin/python scripts/validate-platform-assignments.py
```

Connecting a platform is still done in Switch Console. The manifest stores
only connection names, never tokens. Once a connection exists, provisioning
creates or adopts one room per identity/platform pair and invites the existing
Pulse identity into it. This keeps Telegram, Slack, Discord, and Mattermost as
different entry points into the same audience-scoped memory.

The first local onboarding control plane is available with:

```bash
./scripts/run-control-plane.sh
```

It serves the landing page at `http://127.0.0.1:4173` and exposes credential-free
workspace, connection metadata, assignment validation, health, and provisioning
plan endpoints under `/api`. Raw bot tokens are rejected by design; production
platform adapters will use OAuth/install grants and Switch's encrypted
connection store.

Signals submitted to `POST /api/signals` are now written into the shared
`memory-mcp/pulse.sqlite3` store. `GET /api/brief?audience=...` reads from that
same store, so adapter events and agent queries share one source of truth.

The first adapter worker is ready for Telegram long polling:

```bash
PULSE_TELEGRAM_BOT_TOKEN='token-from-secret-store' \
PULSE_TELEGRAM_VISIBILITY=public \
PULSE_TELEGRAM_ROOM=community \
./scripts/run-telegram-worker.sh
```

The worker never prints the token. Run separate workers for separate audience
rooms; for example, the Supervisor worker uses `PULSE_TELEGRAM_VISIBILITY=private`.

Slack Events API callbacks are accepted by the companion webhook worker:

```bash
SLACK_SIGNING_SECRET='secret-from-slack' \
PULSE_SLACK_VISIBILITY=internal \
PULSE_SLACK_ROOM=team \
./scripts/run-slack-webhook.sh
```

Configure Slack's request URL to the deployed worker's `/` endpoint. URL
verification and signed-request validation are handled before messages enter
Pulse.

For the current Codex-backed local agents, Switch gives each session its own
`CODEX_HOME`. Run `scripts/configure-switch-mcp.sh` after provisioning the
agents; it registers the same launcher in each session config. The launcher
maps the managed working directory to the audience and fails closed for any
unknown directory. The SQLite server repeats the audience check on every read
and write.

## Security and limits

Visibility is enforced in SQLite queries and write validation, not only in
instructions. Public callers cannot read or write internal/private signals;
internal callers cannot read private signals. Messages remain untrusted text,
so prompt injection is possible if an agent ignores its instructions. The demo
does not claim perfect semantic classification or production-grade identity
management. Per-message turns are intentional for the demo; a batch classifier
could later write the same normalized signals.

## Demo

The final demo will show a seeded brief, a public prompt-injection refusal, a
supervisor draft, explicit approval, and the resulting public post. Demo video:
TODO.
