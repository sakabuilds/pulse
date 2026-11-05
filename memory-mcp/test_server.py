from pathlib import Path

import pytest

from server import MemoryStore


def test_public_audience_cannot_record_or_read_internal(tmp_path: Path) -> None:
    db = tmp_path / "pulse.sqlite3"
    private = MemoryStore(db, "private")
    private.record_signal(
        source="team", room="team", visibility="internal", author="Sam", type="blocker",
        topic_key="login-mobile", summary="Auth refresh fails on Android",
    )

    public = MemoryStore(db, "public")
    assert public.search_signals(query="Android") == []
    with pytest.raises(PermissionError):
        public.record_signal(
            source="test", room="community", visibility="internal", author="x", type="issue",
            topic_key="secret", summary="must be rejected",
        )


def test_internal_can_read_public_but_not_private(tmp_path: Path) -> None:
    db = tmp_path / "pulse.sqlite3"
    private = MemoryStore(db, "private")
    private.record_signal(source="x", room="community", visibility="public", author="x", type="praise", topic_key="a", summary="great")
    private.record_signal(source="x", room="supervisor", visibility="private", author="x", type="decision", topic_key="b", summary="secret")
    internal = MemoryStore(db, "internal")
    assert len(internal.search_signals()) == 1
    assert internal.search_signals(query="secret") == []


def test_supervisor_approval_loop(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "pulse.sqlite3", "private")
    reply = store.draft_reply("pricing", "We are investigating this.", "community")
    assert store.list_pending()[0]["id"] == reply["reply_id"]
    assert store.approve_reply(reply["reply_id"])["status"] == "approved"
