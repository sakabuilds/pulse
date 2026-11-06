"""Dispatch approved Pulse replies to a Switch/platform publisher callback."""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

from switch_gateway import SwitchGatewayClient, publish_reply_with_gateway


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


def dispatch_switch_once(control_url: str, *, switch_client: SwitchGatewayClient, agent_name: str | None = None, agent_token: str | None = None, agent_tokens: dict[str, str] | None = None) -> int:
    """Deliver approved replies directly to Switch and acknowledge each one."""
    with urllib.request.urlopen(f"{control_url.rstrip('/')}/api/outbox", timeout=10) as response:
        replies = json.loads(response.read())["replies"]
    delivered = 0
    for reply in replies:
        selected_agent = reply.get("agent") or agent_name
        if not selected_agent:
            raise ValueError(f"approved reply {reply['reply_id']} has no Pulse agent")
        selected_token = (agent_tokens or {}).get(selected_agent) or agent_token
        if not selected_token:
            raise ValueError(f"no Switch API key configured for {selected_agent}")
        publish_reply_with_gateway(reply, client=switch_client, agent_name=selected_agent, room_name=reply["target_room"], agent_token=selected_token)
        body = json.dumps({"publisher": "switch-native"}).encode()
        request = urllib.request.Request(f"{control_url.rstrip('/')}/api/outbox/{reply['reply_id']}/delivered", data=body, method="POST", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=10):
            pass
        delivered += 1
    return delivered


if __name__ == "__main__":
    control_url = os.environ.get("PULSE_CONTROL_URL", "http://127.0.0.1:4173")
    if os.environ.get("PULSE_SWITCH_AGENT_NAME"):
        tokens = json.loads(os.environ["PULSE_SWITCH_AGENT_TOKENS"]) if os.environ.get("PULSE_SWITCH_AGENT_TOKENS") else None
        dispatch_switch_once(control_url, switch_client=SwitchGatewayClient.from_env(), agent_name=os.environ["PULSE_SWITCH_AGENT_NAME"], agent_token=os.environ.get("PULSE_SWITCH_AGENT_TOKEN"), agent_tokens=tokens)
    else:
        dispatch_once(control_url, os.environ["PULSE_PUBLISH_URL"])
