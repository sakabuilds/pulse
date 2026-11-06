"""Discover live Switch IDs through the Gateway and publish Pulse replies."""

from __future__ import annotations

import http.cookiejar
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class SwitchGatewayError(RuntimeError):
    pass


def _json_request(opener: urllib.request.OpenerDirector, url: str, *, method: str = "GET", body: dict[str, Any] | None = None) -> Any:
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(url, data=data, method=method, headers={"Accept": "application/json", "Content-Type": "application/json"})
    try:
        with opener.open(request, timeout=15) as response:
            raw = response.read()
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")
        raise SwitchGatewayError(f"Switch Gateway request failed ({error.code}): {detail[:240]}") from error
    try:
        return json.loads(raw)
    except json.JSONDecodeError as error:
        raise SwitchGatewayError("Switch Gateway returned invalid JSON") from error


@dataclass
class SwitchGatewayClient:
    base_url: str
    opener: urllib.request.OpenerDirector

    @classmethod
    def from_env(cls) -> "SwitchGatewayClient":
        email = os.environ.get("PULSE_SWITCH_EMAIL")
        password = os.environ.get("PULSE_SWITCH_PASSWORD")
        if not email or not password:
            raise SwitchGatewayError("PULSE_SWITCH_EMAIL and PULSE_SWITCH_PASSWORD are required")
        base_url = os.environ.get("PULSE_SWITCH_URL", "http://127.0.0.1:44997").rstrip("/")
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        _json_request(opener, f"{base_url}/gateway/auth/login", method="POST", body={"email": email, "password": password})
        return cls(base_url, opener)

    def agents(self) -> list[dict[str, Any]]:
        value = _json_request(self.opener, f"{self.base_url}/gateway/agents")
        return value if isinstance(value, list) else value.get("items", [])

    def rooms(self) -> list[dict[str, Any]]:
        value = _json_request(self.opener, f"{self.base_url}/gateway/rooms")
        return value if isinstance(value, list) else value.get("items", [])

    def find_agent(self, name: str) -> dict[str, Any]:
        for agent in self.agents():
            if agent.get("name") == name or agent.get("display_name") == name:
                return agent
        raise SwitchGatewayError(f"Switch agent not found: {name}")

    def find_room(self, name: str) -> dict[str, Any]:
        for room in self.rooms():
            if room.get("name") == name or room.get("title") == name:
                return room
        raise SwitchGatewayError(f"Switch room not found: {name}")


def publish_reply_with_gateway(reply: dict[str, Any], *, client: SwitchGatewayClient, agent_name: str, room_name: str, agent_token: str) -> None:
    agent = client.find_agent(agent_name)
    room = client.find_room(room_name)
    agent_id = agent.get("id")
    room_id = room.get("id")
    if not agent_id or not room_id:
        raise SwitchGatewayError("Switch agent or room discovery result has no id")
    payload = json.dumps({"room_id": room_id, "content": reply["draft"]}).encode()
    request = urllib.request.Request(
        f"{client.base_url}/agents/{agent_id}/message",
        data=payload,
        method="POST",
        headers={"Accept": "application/json", "Content-Type": "application/json", "Authorization": f"Bearer {agent_token}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            if response.status >= 300:
                raise SwitchGatewayError(f"Switch rejected the room message ({response.status})")
    except urllib.error.HTTPError as error:
        raise SwitchGatewayError(f"Switch rejected the room message ({error.code})") from error


if __name__ == "__main__":
    raise SystemExit("Import SwitchGatewayClient from the outbox worker after configuring the Pulse and Switch credentials")
