import hashlib
import hmac
import time

from slack_webhook import normalize_event, valid_signature


def test_normalize_slack_message():
    signal = normalize_event({"type": "message", "text": "login still fails?", "user": "U123", "channel": "C123"}, visibility="internal", room="team")
    assert signal["source"] == "slack"
    assert signal["type"] == "question"
    assert signal["visibility"] == "internal"


def test_slack_signature():
    secret = "secret"
    timestamp = str(int(time.time()))
    body = b'{"type":"event_callback"}'
    digest = hmac.new(secret.encode(), b"v0:" + timestamp.encode() + b":" + body, hashlib.sha256).hexdigest()
    assert valid_signature(body, timestamp, f"v0={digest}", secret)

