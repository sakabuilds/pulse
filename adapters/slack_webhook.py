"""Receive Slack Events API callbacks and forward normalized messages to Pulse."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


def normalize_event(event: dict[str, Any], *, visibility: str, room: str) -> dict[str, str] | None:
    if event.get("type") != "message" or event.get("subtype") or not event.get("text"):
        return None
    text = " ".join(str(event["text"]).split())
    return {"source": "slack", "room": room or str(event.get("channel", "slack")), "visibility": visibility,
            "type": "question" if text.endswith("?") else "issue", "topic_key": "slack-general",
            "summary": text[:1000], "author": str(event.get("user", "slack-user"))}


def valid_signature(body: bytes, timestamp: str, signature: str, secret: str) -> bool:
    if not timestamp or not signature or not secret or abs(time.time() - int(timestamp)) > 300:
        return False
    digest = hmac.new(secret.encode(), b"v0:" + timestamp.encode() + b":" + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, f"v0={digest}")


class SlackHandler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        return

    def do_POST(self):  # noqa: N802
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        secret = os.environ.get("SLACK_SIGNING_SECRET", "")
        if secret and not valid_signature(body, self.headers.get("X-Slack-Request-Timestamp", ""), self.headers.get("X-Slack-Signature", ""), secret):
            self.send_response(401)
            self.end_headers()
            return
        payload = json.loads(body or b"{}")
        if payload.get("type") == "url_verification":
            self.send_json(200, {"challenge": payload.get("challenge", "")})
            return
        event = payload.get("event", {})
        signal = normalize_event(event, visibility=os.environ.get("PULSE_SLACK_VISIBILITY", "internal"), room=os.environ.get("PULSE_SLACK_ROOM", "team"))
        if signal:
            request = urllib.request.Request(os.environ.get("PULSE_CONTROL_URL", "http://127.0.0.1:4173") + "/api/signals", data=json.dumps(signal).encode(), method="POST", headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=10):
                pass
        self.send_json(200, {"ok": True, "ingested": bool(signal)})

    def send_json(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    port = int(os.environ.get("PULSE_SLACK_PORT", "8081"))
    ThreadingHTTPServer(("127.0.0.1", port), SlackHandler).serve_forever()
