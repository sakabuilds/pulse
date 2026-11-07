"""Credential-free local Pulse onboarding and platform-routing control plane."""

from __future__ import annotations

import json
import importlib.util
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = Path(os.getenv("PULSE_CONTROL_STATE", ROOT / "control-plane" / "state.json"))
WEB_ROOT = ROOT / "web"
SUPPORTED = {"telegram", "slack", "discord", "mattermost", "teams"}
MODES = {"community", "team", "supervisor"}
DEFAULT_STATE = {"workspace": {"name": "My Pulse workspace", "created": False}, "connections": {}, "assignments": {
    "community": {"room_type": "shared", "platforms": []},
    "team": {"room_type": "shared", "platforms": []},
    "supervisor": {"room_type": "private", "platforms": []},
}, "signals": [], "replies": []}
VISIBILITY_RANK = {"public": 0, "internal": 1, "private": 2}
SIGNAL_TYPES = {"bug", "feature", "complaint", "question", "praise", "decision", "blocker", "issue", "pr", "ci"}
MEMORY_DB = Path(os.getenv("PULSE_MEMORY_DB", ROOT / "memory-mcp" / "pulse.sqlite3"))


def memory_store(audience="private"):
    module_path = ROOT / "memory-mcp" / "server.py"
    spec = importlib.util.spec_from_file_location("pulse_memory_runtime", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load Pulse memory runtime")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.MemoryStore(MEMORY_DB, audience)


def load_state():
    return json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else json.loads(json.dumps(DEFAULT_STATE))


def save_state(state):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp = STATE_PATH.with_suffix(".tmp")
    temp.write_text(json.dumps(state, indent=2) + "\n")
    temp.replace(STATE_PATH)


def validate_assignments(assignments, connections):
    if set(assignments) != MODES:
        raise ValueError("assignments must include community, team, and supervisor")
    if assignments["supervisor"].get("room_type") != "private":
        raise ValueError("Supervisor must always use a private room")
    for mode, config in assignments.items():
        if config.get("room_type") not in {"private", "shared"}:
            raise ValueError(f"invalid room type for {mode}")
        platforms = config.get("platforms", [])
        if not isinstance(platforms, list) or any(p not in SUPPORTED for p in platforms):
            raise ValueError(f"invalid platform assignment for {mode}")
        missing = [p for p in platforms if p not in connections]
        if missing:
            raise ValueError(f"connect these platforms first: {', '.join(missing)}")


def provisioning_plan(state):
    validate_assignments(state["assignments"], state["connections"])
    return [{"agent": f"pulse-{mode}", "platform": platform, "room_type": config["room_type"],
             "room_name": f"pulse-{mode}-{platform}",
             "action": "adopt_private_room" if config["room_type"] == "private" else "adopt_or_create_room",
             "status": "ready" if state["connections"][platform].get("status") == "connected" else "blocked"}
            for mode, config in state["assignments"].items() for platform in config["platforms"]]


def visible_signals(state, audience):
    if audience not in VISIBILITY_RANK:
        raise ValueError(f"invalid audience: {audience}")
    max_rank = VISIBILITY_RANK[audience]
    return [signal for signal in state.get("signals", []) if VISIBILITY_RANK[signal["visibility"]] <= max_rank]


class Handler(BaseHTTPRequestHandler):
    server_version = "PulseControl/0.1"

    def log_message(self, *_):
        return

    def send_json(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def read_json(self):
        return json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")

    def do_GET(self):  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/state":
            self.send_json(200, load_state())
        elif path == "/api/provisioning-plan":
            try:
                self.send_json(200, {"plan": provisioning_plan(load_state())})
            except ValueError as error:
                self.send_json(422, {"error": str(error)})
        elif path == "/api/brief":
            try:
                audience = urlparse(self.path).query.removeprefix("audience=") or "private"
                signals = memory_store(audience).search_signals()
                self.send_json(200, {"audience": audience, "signal_count": len(signals), "signals": signals})
            except ValueError as error:
                self.send_json(422, {"error": str(error)})
        elif path == "/api/outbox":
            self.send_json(200, {"replies": [reply for reply in load_state().get("replies", []) if reply["status"] == "approved"]})
        elif path == "/api/health":
            self.send_json(200, {"status": "ok"})
        else:
            self.serve_file(path)

    def do_POST(self):  # noqa: N802
        state = load_state()
        path = urlparse(self.path).path
        try:
            payload = self.read_json()
            if path == "/api/workspace":
                name = str(payload.get("name", "")).strip()
                if not name:
                    raise ValueError("workspace name is required")
                state["workspace"] = {"name": name, "created": True}
            elif path == "/api/assignments":
                validate_assignments(payload, state["connections"])
                state["assignments"] = payload
            elif path == "/api/connections":
                platform = payload.get("platform")
                if platform not in SUPPORTED:
                    raise ValueError(f"unsupported platform: {platform}")
                if any(key in payload for key in ("token", "access_token", "secret")):
                    raise ValueError("raw credentials are not accepted; use the platform OAuth flow")
                state["connections"][platform] = {"label": payload.get("label", platform.title()), "status": payload.get("status", "pending_oauth")}
            elif path == "/api/signals":
                visibility = payload.get("visibility", "public")
                signal_type = payload.get("type", "issue")
                if visibility not in VISIBILITY_RANK:
                    raise ValueError(f"invalid visibility: {visibility}")
                if signal_type not in SIGNAL_TYPES:
                    raise ValueError(f"invalid signal type: {signal_type}")
                summary = str(payload.get("summary", "")).strip()
                if not summary:
                    raise ValueError("signal summary is required")
                signal = {
                    "source": str(payload.get("source", "adapter")),
                    "room": str(payload.get("room", "unknown")),
                    "visibility": visibility,
                    "type": signal_type,
                    "topic_key": str(payload.get("topic_key", "general")),
                    "summary": summary,
                }
                state.setdefault("signals", []).append(signal)
                memory_store("private").record_signal(author="adapter", quote="", severity="", url="", **signal)
            elif path == "/api/replies":
                topic_key = str(payload.get("topic_key", "")).strip()
                draft = str(payload.get("draft", "")).strip()
                target_room = str(payload.get("target_room", "")).strip()
                agent = str(payload.get("agent", "pulse-supervisor")).strip()
                if not topic_key or not draft or not target_room or not agent:
                    raise ValueError("topic_key, draft, target_room, and agent are required")
                if not agent.startswith("pulse-"):
                    raise ValueError("agent must be a Pulse agent name")
                result = memory_store("private").draft_reply(topic_key, draft, target_room)
                state.setdefault("replies", []).append({"reply_id": result["reply_id"], "topic_key": topic_key, "draft": draft, "target_room": target_room, "agent": agent, "status": "pending"})
            elif path.startswith("/api/replies/") and path.endswith("/approve"):
                reply_id = path.split("/")[3]
                if payload.get("audience") != "private":
                    raise ValueError("only the private Supervisor audience may approve replies")
                result = memory_store("private").approve_reply(reply_id)
                for reply in state.setdefault("replies", []):
                    if reply["reply_id"] == reply_id:
                        reply["status"] = result["status"]
                        break
            elif path.startswith("/api/outbox/") and path.endswith("/delivered"):
                reply_id = path.split("/")[3]
                publisher = str(payload.get("publisher", "switch"))
                for reply in state.setdefault("replies", []):
                    if reply["reply_id"] == reply_id and reply["status"] == "approved":
                        reply["status"] = "posted"
                        reply["publisher"] = publisher
                        break
                else:
                    raise ValueError("approved reply not found")
                with memory_store("private").connect() as db:
                    db.execute("UPDATE replies SET status = 'posted' WHERE id = ? AND status = 'approved'", (reply_id,))
                    db.commit()
            elif path == "/api/provision":
                plan = provisioning_plan(state)
                if any(item["status"] == "blocked" for item in plan):
                    raise ValueError("all assigned platforms must be connected before provisioning")
                for item in plan:
                    item["status"] = "planned"
                save_state(state)
                self.send_json(200, {"plan": plan})
                return
            else:
                self.send_json(404, {"error": "not found"})
                return
            save_state(state)
            self.send_json(200, state)
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json(422, {"error": str(error)})

    def serve_file(self, path):
        target = (WEB_ROOT / ("index.html" if path == "/" else path.lstrip("/"))).resolve()
        if WEB_ROOT not in target.parents or not target.is_file():
            self.send_json(404, {"error": "not found"})
            return
        content_type = {".html": "text/html", ".css": "text/css", ".js": "text/javascript"}.get(target.suffix, "application/octet-stream")
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    port = int(os.getenv("PULSE_CONTROL_PORT", "4173"))
    print(f"Pulse control plane: http://127.0.0.1:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
