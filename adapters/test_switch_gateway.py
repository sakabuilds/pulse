import json
from unittest.mock import patch

from switch_gateway import SwitchGatewayClient, SwitchGatewayError, publish_reply_with_gateway


class FakeResponse:
    status = 200

    def __init__(self, value):
        self.value = value

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return json.dumps(self.value).encode()


class FakeOpener:
    def open(self, request, timeout=15):
        if request.full_url.endswith("/agents"):
            return FakeResponse([{"id": "agent-1", "name": "pulse-community"}])
        if request.full_url.endswith("/rooms"):
            return FakeResponse([{"id": "room-1", "name": "community"}])
        raise AssertionError(request.full_url)


def test_discovery_resolves_names_and_posts_native_message():
    client = SwitchGatewayClient("http://switch", FakeOpener())
    with patch("switch_gateway.urllib.request.urlopen") as open_url:
        open_url.return_value.__enter__.return_value.status = 200
        publish_reply_with_gateway({"draft": "Hello"}, client=client, agent_name="pulse-community", room_name="community", agent_token="agent-secret")
        request = open_url.call_args.args[0]
    assert request.full_url.endswith("/agents/agent-1/message")
    assert json.loads(request.data) == {"room_id": "room-1", "content": "Hello"}
    assert request.get_header("Authorization") == "Bearer agent-secret"


def test_missing_names_are_actionable():
    client = SwitchGatewayClient("http://switch", FakeOpener())
    try:
        client.find_agent("missing")
    except SwitchGatewayError as error:
        assert "Switch agent not found" in str(error)
    else:
        raise AssertionError("expected discovery failure")
