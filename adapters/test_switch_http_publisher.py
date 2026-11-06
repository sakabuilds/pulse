import json
from unittest.mock import patch

from switch_http_publisher import publish_to_switch


def test_switch_agent_message_payload():
    reply = {"draft": "Approved update"}
    with patch("switch_http_publisher.urllib.request.urlopen") as open_url:
        open_url.return_value.__enter__.return_value.status = 200
        publish_to_switch(reply, switch_url="http://switch", agent_id="agent-1", room_id="room-1", bearer_token="token")
        request = open_url.call_args.args[0]
        assert request.full_url.endswith("/agents/agent-1/message")
        assert json.loads(request.data) == {"room_id": "room-1", "content": "Approved update"}
        assert request.get_header("Authorization") == "Bearer token"

