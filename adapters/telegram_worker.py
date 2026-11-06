"""Forward Telegram bot messages into Pulse's normalized signal API.

The bot token is read only from the environment and is never logged. Room
audience is configured per worker so the same Pulse installation can run a
private Supervisor worker separately from public Community workers.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


def normalize_message(update: dict[str, Any], *, visibility: str, room: str) -> dict[str, str] | None:
    message = update.get("message") or update.get("channel_post")
    if not message or not message.get("text"):
        return None
    sender = message.get("from") or {}
    chat = message.get("chat") or {}
    author = sender.get("username") or sender.get("first_name") or "telegram-user"
    chat_name = chat.get("title") or chat.get("username") or str(chat.get("id", room))
    text = " ".join(str(message["text"]).split())
    return {
        "source": "telegram",
        "room": room or chat_name,
        "visibility": visibility,
        "type": "question" if text.endswith("?") else "issue",
        "topic_key": "telegram-general",
        "summary": text[:1000],
        "author": author,
    }


class TelegramWorker:
    def __init__(self, token: str, control_url: str, visibility: str, room: str, offset_path: Path) -> None:
        if not token:
            raise ValueError("PULSE_TELEGRAM_BOT_TOKEN is required")
        self.token = token
        self.control_url = control_url.rstrip("/")
        self.visibility = visibility
        self.room = room
        self.offset_path = offset_path

    @property
    def api_base(self) -> str:
        return f"https://api.telegram.org/bot{self.token}"

    def telegram(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        encoded = urllib.parse.urlencode(params or {}).encode()
        request = urllib.request.Request(f"{self.api_base}/{method}", data=encoded, method="POST")
        with urllib.request.urlopen(request, timeout=45) as response:
            payload = json.loads(response.read())
        if not payload.get("ok"):
            raise RuntimeError(f"Telegram API error in {method}")
        return payload["result"]

    def send_signal(self, signal: dict[str, str]) -> None:
        body = json.dumps(signal).encode()
        request = urllib.request.Request(f"{self.control_url}/api/signals", data=body, method="POST", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status >= 300:
                raise RuntimeError("Pulse signal ingestion rejected the Telegram event")

    def run_once(self) -> int:
        offset = int(self.offset_path.read_text()) if self.offset_path.exists() else 0
        updates = self.telegram("getUpdates", {"offset": offset, "timeout": 30, "allowed_updates": json.dumps(["message", "channel_post"])})
        handled = 0
        for update in updates:
            self.offset_path.parent.mkdir(parents=True, exist_ok=True)
            self.offset_path.write_text(str(update["update_id"] + 1))
            signal = normalize_message(update, visibility=self.visibility, room=self.room)
            if signal is not None:
                self.send_signal(signal)
                handled += 1
        return handled

    def run_forever(self) -> None:
        while True:
            try:
                self.run_once()
            except (OSError, RuntimeError, urllib.error.URLError):
                time.sleep(3)


def main() -> None:
    worker = TelegramWorker(
        token=os.environ.get("PULSE_TELEGRAM_BOT_TOKEN", ""),
        control_url=os.environ.get("PULSE_CONTROL_URL", "http://127.0.0.1:4173"),
        visibility=os.environ.get("PULSE_TELEGRAM_VISIBILITY", "public"),
        room=os.environ.get("PULSE_TELEGRAM_ROOM", "telegram"),
        offset_path=Path(os.environ.get("PULSE_TELEGRAM_OFFSET", ".pulse/telegram.offset")),
    )
    worker.run_forever()


if __name__ == "__main__":
    main()
