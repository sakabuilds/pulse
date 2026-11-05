"""PULSE memory MCP server with database-enforced audience boundaries."""

from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from mcp.server.fastmcp import FastMCP

VISIBILITY_RANK = {"public": 0, "internal": 1, "private": 2}
SIGNAL_TYPES = {"bug", "feature", "complaint", "question", "praise", "decision", "blocker", "issue", "pr", "ci"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MemoryStore:
    def __init__(self, path: str | Path, audience: str = "private") -> None:
        if audience not in VISIBILITY_RANK:
            raise ValueError(f"invalid audience: {audience}")
        self.path = str(path)
        self.audience = audience
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        return db

    def _init_db(self) -> None:
        with closing(self.connect()) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    room TEXT NOT NULL,
                    visibility TEXT NOT NULL CHECK (visibility IN ('public','internal','private')),
                    author TEXT NOT NULL,
                    type TEXT NOT NULL,
                    topic_key TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    quote TEXT,
                    severity TEXT,
                    url TEXT,
                    created_at TEXT NOT NULL,
                    assignee TEXT
                );
                CREATE TABLE IF NOT EXISTS replies (
                    id TEXT PRIMARY KEY,
                    topic_key TEXT NOT NULL,
                    draft TEXT NOT NULL,
                    target_room TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('pending','approved','posted')),
                    created_at TEXT NOT NULL,
                    approved_at TEXT
                );
                CREATE TABLE IF NOT EXISTS signal_links (
                    signal_id INTEGER NOT NULL,
                    linked_signal_id INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    PRIMARY KEY (signal_id, linked_signal_id),
                    FOREIGN KEY (signal_id) REFERENCES signals(id),
                    FOREIGN KEY (linked_signal_id) REFERENCES signals(id)
                );
                """
            )
            db.commit()

    def _check_visibility(self, visibility: str) -> None:
        if visibility not in VISIBILITY_RANK:
            raise ValueError(f"invalid visibility: {visibility}")
        if VISIBILITY_RANK[visibility] > VISIBILITY_RANK[self.audience]:
            raise PermissionError(f"{self.audience} audience cannot access {visibility} data")

    def record_signal(self, *, source: str, room: str, visibility: str, author: str, type: str,
                      topic_key: str, summary: str, quote: str = "", severity: str = "",
                      url: str = "") -> dict[str, Any]:
        self._check_visibility(visibility)
        if type not in SIGNAL_TYPES:
            raise ValueError(f"invalid signal type: {type}")
        with closing(self.connect()) as db:
            cur = db.execute(
                """INSERT INTO signals
                (source, room, visibility, author, type, topic_key, summary, quote, severity, url, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (source, room, visibility, author, type, topic_key, summary, quote, severity, url, utc_now()),
            )
            db.commit()
            return {"id": cur.lastrowid, "topic_key": topic_key, "visibility": visibility}

    def _visible_clause(self) -> tuple[str, tuple[Any, ...]]:
        allowed = [name for name, rank in VISIBILITY_RANK.items() if rank <= VISIBILITY_RANK[self.audience]]
        return ",".join("?" for _ in allowed), tuple(allowed)

    def search_signals(self, query: str = "", type: str = "", source: str = "", since: str = "") -> list[dict[str, Any]]:
        placeholders, allowed = self._visible_clause()
        sql = f"SELECT * FROM signals WHERE visibility IN ({placeholders})"
        params: list[Any] = list(allowed)
        if query:
            sql += " AND (summary LIKE ? OR quote LIKE ? OR topic_key LIKE ?)"
            params.extend([f"%{query}%"] * 3)
        if type:
            sql += " AND type = ?"
            params.append(type)
        if source:
            sql += " AND source = ?"
            params.append(source)
        if since:
            sql += " AND created_at >= ?"
            params.append(since)
        sql += " ORDER BY created_at DESC, id DESC"
        with closing(self.connect()) as db:
            return [dict(row) for row in db.execute(sql, params).fetchall()]

    def brief(self, since: str = "") -> dict[str, Any]:
        signals = self.search_signals(since=since)
        topics: dict[str, dict[str, Any]] = {}
        for signal in signals:
            topic = topics.setdefault(signal["topic_key"], {"topic_key": signal["topic_key"], "signals": [], "latest": signal["created_at"]})
            topic["signals"].append(signal)
        return {"audience": self.audience, "signal_count": len(signals), "topics": list(topics.values())}

    def link_signals(self, signal_ids: list[int], reason: str) -> dict[str, Any]:
        if len(signal_ids) < 2:
            raise ValueError("at least two signal IDs are required")
        visible = {row["id"] for row in self.search_signals()}
        if not set(signal_ids).issubset(visible):
            raise PermissionError("cannot link a signal outside this audience")
        with closing(self.connect()) as db:
            for left in signal_ids:
                for right in signal_ids:
                    if left != right:
                        db.execute("INSERT OR IGNORE INTO signal_links VALUES (?, ?, ?)", (left, right, reason))
            db.commit()
        return {"linked": signal_ids, "reason": reason}

    def assign(self, topic_key: str, assignee: str) -> dict[str, Any]:
        with closing(self.connect()) as db:
            cur = db.execute("UPDATE signals SET assignee = ? WHERE topic_key = ? AND visibility IN ('public','internal','private')", (assignee, topic_key))
            db.commit()
        return {"topic_key": topic_key, "assignee": assignee, "updated": cur.rowcount}

    def draft_reply(self, topic_key: str, draft: str, target_room: str) -> dict[str, Any]:
        if target_room == "community" and self.audience != "private":
            raise PermissionError("only the private supervisor audience may draft community replies")
        reply_id = str(uuid4())
        with closing(self.connect()) as db:
            db.execute("INSERT INTO replies VALUES (?, ?, ?, ?, 'pending', ?, NULL)", (reply_id, topic_key, draft, target_room, utc_now()))
            db.commit()
        return {"reply_id": reply_id, "status": "pending"}

    def approve_reply(self, reply_id: str) -> dict[str, Any]:
        if self.audience != "private":
            raise PermissionError("only the private supervisor audience may approve replies")
        with closing(self.connect()) as db:
            cur = db.execute("UPDATE replies SET status = 'approved', approved_at = ? WHERE id = ? AND status = 'pending'", (utc_now(), reply_id))
            db.commit()
        if cur.rowcount != 1:
            raise ValueError("pending reply not found")
        return {"reply_id": reply_id, "status": "approved"}

    def list_pending(self) -> list[dict[str, Any]]:
        with closing(self.connect()) as db:
            return [dict(row) for row in db.execute("SELECT * FROM replies WHERE status = 'pending' ORDER BY created_at").fetchall()]


DB_PATH = os.getenv("PULSE_DB", str(Path(__file__).with_name("pulse.sqlite3")))
AUDIENCE = os.getenv("PULSE_AUDIENCE", "private")
store = MemoryStore(DB_PATH, AUDIENCE)
mcp = FastMCP("pulse-memory")


@mcp.tool()
def record_signal(source: str, room: str, visibility: str, author: str, type: str, topic_key: str, summary: str,
                  quote: str = "", severity: str = "", url: str = "") -> dict[str, Any]:
    return store.record_signal(source=source, room=room, visibility=visibility, author=author, type=type,
                               topic_key=topic_key, summary=summary, quote=quote, severity=severity, url=url)


@mcp.tool()
def search_signals(query: str = "", type: str = "", source: str = "", since: str = "") -> list[dict[str, Any]]:
    return store.search_signals(query=query, type=type, source=source, since=since)


@mcp.tool()
def brief(since: str = "") -> dict[str, Any]:
    return store.brief(since)


@mcp.tool()
def link_signals(signal_ids: list[int], reason: str) -> dict[str, Any]:
    return store.link_signals(signal_ids, reason)


@mcp.tool()
def assign(topic_key: str, assignee: str) -> dict[str, Any]:
    return store.assign(topic_key, assignee)


@mcp.tool()
def draft_reply(topic_key: str, draft: str, target_room: str) -> dict[str, Any]:
    return store.draft_reply(topic_key, draft, target_room)


@mcp.tool()
def approve_reply(reply_id: str) -> dict[str, Any]:
    return store.approve_reply(reply_id)


@mcp.tool()
def list_pending() -> list[dict[str, Any]]:
    return store.list_pending()


if __name__ == "__main__":
    mcp.run(transport=os.getenv("MCP_TRANSPORT", "stdio"))
