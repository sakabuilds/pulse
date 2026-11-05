#!/usr/bin/env python3
"""Seed deterministic PULSE signals for a repeatable demo."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "memory-mcp"))
from server import MemoryStore  # noqa: E402


MESSAGES = [
    ("community", "public", "Amina", "bug", "login-mobile", "Login fails on Android after the latest update.", "I get sent back to the login screen.", "high"),
    ("community", "public", "Diego", "complaint", "export-slow", "CSV export takes more than five minutes for a small report.", "Still waiting after 7 minutes.", "medium"),
    ("community", "public", "Rina", "question", "pricing-confusing", "The pricing page does not make the team plan limits clear.", "Which plan includes audit logs?", "low"),
    ("community", "public", "Noah", "feature", "bulk-invite", "Please add bulk invite for new teammates.", "Inviting 40 people one by one is painful.", "low"),
    ("community", "public", "Lena", "praise", "general", "The new dashboard is much easier to scan.", "The filters are fantastic.", ""),
    ("community", "public", "Bot", "question", "noise", "Does anyone know a good coffee shop nearby?", "", ""),
    ("team", "internal", "Sam", "blocker", "login-mobile", "Android login failure reproduced on Pixel 7.", "Refresh token is rejected after rotation.", "high"),
    ("team", "internal", "Ife", "decision", "login-mobile", "We will patch refresh-token rotation before investigating UI changes.", "Keep the workaround out of the public reply.", "high"),
    ("team", "internal", "Maya", "issue", "export-slow", "Profiling shows export workers queue behind PDF jobs.", "The queue is shared unexpectedly.", "medium"),
    ("team", "internal", "Sam", "decision", "pricing-confusing", "Product will rewrite the comparison table this sprint.", "Legal copy still needs review.", "low"),
    ("team", "internal", "Noah", "feature", "bulk-invite", "Bulk invite is scoped for the next planning session.", "Needs rate-limit design.", "low"),
]

EXTRA = [
    ("community", "public", "Ari", "bug", "login-mobile", "Android login loops after a password reset.", "It works on desktop but not my phone.", "high"),
    ("community", "public", "Zoe", "complaint", "export-slow", "Exports are still slow during the morning peak.", "The progress bar stops at 80 percent.", "medium"),
    ("community", "public", "Ben", "question", "pricing-confusing", "I cannot tell if SSO is included in the team plan.", "The plan cards look almost identical.", "low"),
    ("community", "public", "Mira", "feature", "saved-views", "Saved report views would make weekly reviews easier.", "Please remember my filters.", "low"),
    ("community", "public", "Tobi", "praise", "general", "Support answered my setup question quickly.", "Nice work on the response time.", ""),
    ("community", "public", "Nia", "question", "noise", "Is there a keyboard shortcut for search?", "", ""),
    ("team", "internal", "Ife", "issue", "login-mobile", "The refresh token error only occurs when the app resumes from background.", "Cold starts are unaffected.", "high"),
    ("team", "internal", "Maya", "decision", "export-slow", "We will split PDF and CSV worker pools.", "Measure queue wait separately.", "medium"),
    ("team", "internal", "Sam", "blocker", "pricing-confusing", "Legal has not approved the revised comparison copy.", "Do not publish the draft yet.", "medium"),
    ("team", "internal", "Noah", "pr", "bulk-invite", "PR 184 adds an invite preview step.", "Waiting for rate-limit review.", "low"),
]

# Repeat realistic follow-ups with stable authors and topics so the demo has
# enough room history to make briefs and grouping meaningful.
for round_number in range(1, 5):
    for room, visibility, author, signal_type, topic, summary, quote, severity in EXTRA:
        MESSAGES.append((room, visibility, f"{author}{round_number}", signal_type, topic,
                         f"{summary} Follow-up {round_number}.", quote, severity))


def main() -> None:
    db = ROOT / "memory-mcp" / "pulse.sqlite3"
    if db.exists():
        db.unlink()
    store = MemoryStore(db, "private")
    for room, visibility, author, signal_type, topic, summary, quote, severity in MESSAGES:
        store.record_signal(
            source="seed", room=room, visibility=visibility, author=author,
            type=signal_type, topic_key=topic, summary=summary, quote=quote,
            severity=severity,
        )
    print(f"Seeded {len(MESSAGES)} deterministic signals into {db}")
    for topic in ("login-mobile", "export-slow", "pricing-confusing"):
        print(f"- {topic}: {len(store.search_signals(query=topic))} signals")


if __name__ == "__main__":
    main()
