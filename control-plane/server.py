"""Credential-free local Pulse onboarding and platform-routing control plane."""

from __future__ import annotations

import json
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
}}


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


class Handler(BaseHTTPRequestHandler):
    server_version = "PulseControl/0.1"

    def log_message(self, *_):
        return

    def send_json(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

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
