#!/usr/bin/env python3
"""Run a deterministic, credential-free Pulse end-to-end demo."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "adapters"))
from outbox_publisher import dispatch_once  # noqa: E402


class Publisher(BaseHTTPRequestHandler):
    received = []

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        self.received.append(json.loads(self.rfile.read(length)))
        self.send_response(200)
        self.end_headers()

    def log_message(self, *_):
        return


def call(base: str, method: str, path: str, payload=None):
    request = urllib.request.Request(base + path, method=method, headers={"Content-Type": "application/json"})
    if payload is not None:
        request.data = json.dumps(payload).encode()
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read())


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="pulse-demo-") as directory:
        state = Path(directory) / "state.json"
        memory = Path(directory) / "memory.sqlite3"
        os.environ["PULSE_CONTROL_STATE"] = str(state)
        os.environ["PULSE_MEMORY_DB"] = str(memory)
        sys.path.insert(0, str(ROOT / "control-plane"))
        from server import Handler  # noqa: E402
        control = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        control_port = control.server_address[1]
        control_thread = threading.Thread(target=control.serve_forever, daemon=True)
        control_thread.start()
        publisher = ThreadingHTTPServer(("127.0.0.1", 0), Publisher)
        publisher_thread = threading.Thread(target=publisher.serve_forever, daemon=True)
        publisher_thread.start()
        control_url = f"http://127.0.0.1:{control_port}"
        publisher_url = f"http://127.0.0.1:{publisher.server_address[1]}/publish"
        try:
            call(control_url, "POST", "/api/connections", {"platform": "telegram", "status": "connected"})
            call(control_url, "POST", "/api/assignments", {
                "community": {"room_type": "shared", "platforms": []},
                "team": {"room_type": "shared", "platforms": []},
                "supervisor": {"room_type": "private", "platforms": ["telegram"]},
            })
            for visibility, room, summary in [("public", "community", "Export is slow"), ("internal", "team", "We found the export bottleneck"), ("private", "supervisor", "Approve the customer update")]:
                call(control_url, "POST", "/api/signals", {"source": "demo", "room": room, "visibility": visibility, "summary": summary})
            public = call(control_url, "GET", "/api/brief?audience=public")
            private = call(control_url, "GET", "/api/brief?audience=private")
            assert public["signal_count"] == 1 and private["signal_count"] == 3
            draft = call(control_url, "POST", "/api/replies", {"topic_key": "export-slow", "draft": "We are investigating the export delay and will share an update.", "target_room": "community"})
            reply_id = draft["replies"][-1]["reply_id"]
            call(control_url, "POST", f"/api/replies/{reply_id}/approve", {"audience": "private"})
            delivered = dispatch_once(control_url, publisher_url)
            assert delivered == 1 and Publisher.received[0]["target_room"] == "community"
            assert not call(control_url, "GET", "/api/outbox")["replies"]
            print("PULSE demo passed")
            print("- public brief: 1 signal")
            print("- private Supervisor brief: 3 signals")
            print("- approved reply delivered to community")
            return 0
        finally:
            publisher.shutdown()
            control.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
