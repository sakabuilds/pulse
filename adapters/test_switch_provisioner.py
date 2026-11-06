import json
from unittest.mock import patch

from switch_provisioner import provision_once


def test_provision_ready_assignments():
    responses = [
        type("Response", (), {"read": lambda self: json.dumps({"plan": [{"agent": "pulse-supervisor", "platform": "telegram", "room_type": "private", "room_name": "pulse-supervisor-telegram", "status": "ready"}]}).encode(), "__enter__": lambda self: self, "__exit__": lambda *args: None})(),
        type("Response", (), {"status": 200, "__enter__": lambda self: self, "__exit__": lambda *args: None})(),
    ]
    with patch("switch_provisioner.urllib.request.urlopen", side_effect=responses) as open_url:
        assert provision_once("http://control", "http://switch") == 1
        assert json.loads(open_url.call_args_list[1].args[0].data)["room_type"] == "private"

