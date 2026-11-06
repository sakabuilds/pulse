import json
from unittest.mock import patch

from outbox_publisher import publish_reply


def test_publish_payload():
    reply = {"reply_id": "r1", "target_room": "community", "topic_key": "export-slow", "draft": "We are investigating."}
    with patch("outbox_publisher.urllib.request.urlopen") as open_url:
        open_url.return_value.__enter__.return_value.status = 200
        publish_reply(reply, "http://publisher.test/post")
        request = open_url.call_args.args[0]
        assert json.loads(request.data)["target_room"] == "community"
        assert json.loads(request.data)["text"] == "We are investigating."
