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
per room. The memory server is a separate MCP process with an audience setting
per instance. Switch room messages trigger agent turns; the GitHub watcher and
scheduled digest will use the supervisor room as explicit nudges.

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
