"""Publish an approved Pulse reply through Switch's agent message endpoint."""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any


def publish_to_switch(reply: dict[str, Any], *, switch_url: str, agent_id: str, room_id: str, bearer_token: str) -> None:
    payload = json.dumps({"room_id": room_id, "content": reply["draft"]}).encode()
    request = urllib.request.Request(f"{switch_url.rstrip('/')}/agents/{agent_id}/message", data=payload, method="POST", headers={"Content-Type": "application/json", "Authorization": f"Bearer {bearer_token}"})
    with urllib.request.urlopen(request, timeout=15) as response:
        if response.status >= 300:
            raise RuntimeError("Switch rejected the room message")


if __name__ == "__main__":
    raise SystemExit("Use publish_to_switch from the outbox worker after configuring room and agent IDs")
