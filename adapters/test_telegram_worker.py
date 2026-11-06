from telegram_worker import normalize_message


def test_normalize_group_message():
    signal = normalize_message({"update_id": 4, "message": {"text": "  export is very slow  ", "from": {"username": "maya"}, "chat": {"title": "Community"}}}, visibility="public", room="community")
    assert signal == {"source": "telegram", "room": "community", "visibility": "public", "type": "issue", "topic_key": "telegram-general", "summary": "export is very slow", "author": "maya"}


def test_ignore_non_text_update():
    assert normalize_message({"update_id": 5, "message": {"photo": []}}, visibility="public", room="community") is None

