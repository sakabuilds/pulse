"""Dispatch approved Pulse replies to a Switch/platform publisher callback."""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any


def publish_reply(reply: dict[str, Any], publish_url: str) -> None:
    """Send one approved reply to the configured Switch publisher endpoint."""
    payload = json.dumps({"target_room": reply["target_room"], "text": reply["draft"], "topic_key": reply["topic_key"], "reply_id": reply["reply_id"]}).encode()
    request = urllib.request.Request(publish_url, data=payload, method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=15) as response:
        if response.status >= 300:
            raise RuntimeError("publisher rejected the approved reply")


def dispatch_once(control_url: str, publish_url: str) -> int:
    with urllib.request.urlopen(f"{control_url.rstrip('/')}/api/outbox", timeout=10) as response:
        replies = json.loads(response.read())["replies"]
    delivered = 0
    for reply in replies:
        publish_reply(reply, publish_url)
        body = json.dumps({"publisher": publish_url}).encode()
        request = urllib.request.Request(f"{control_url.rstrip('/')}/api/outbox/{reply['reply_id']}/delivered", data=body, method="POST", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=10):
            pass
        delivered += 1
    return delivered


if __name__ == "__main__":
    dispatch_once(os.environ.get("PULSE_CONTROL_URL", "http://127.0.0.1:4173"), os.environ["PULSE_PUBLISH_URL"])
