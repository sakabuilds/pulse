import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def request(base, method, path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(base + path, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=3) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def test_onboarding_guards(tmp_path):
    env = {**os.environ, "PULSE_CONTROL_PORT": "41973", "PULSE_CONTROL_STATE": str(tmp_path / "state.json"), "PULSE_MEMORY_DB": str(tmp_path / "memory.sqlite3")}
    process = subprocess.Popen([sys.executable, "control-plane/server.py"], cwd=ROOT, env=env)
    try:
        base = "http://127.0.0.1:41973"
        for _ in range(30):
            try:
                if request(base, "GET", "/api/health")[0] == 200:
                    break
            except Exception:
                time.sleep(0.05)
        assert request(base, "POST", "/api/connections", {"platform": "telegram", "label": "My Telegram"})[0] == 200
        assert request(base, "POST", "/api/connections", {"platform": "slack", "token": "must-not-store"})[0] == 422
        bad = {"community": {"room_type": "shared", "platforms": []}, "team": {"room_type": "shared", "platforms": []}, "supervisor": {"room_type": "shared", "platforms": ["telegram"]}}
        assert request(base, "POST", "/api/assignments", bad)[0] == 422
        assert request(base, "POST", "/api/signals", {"source": "telegram", "room": "supervisor", "visibility": "private", "summary": "Private launch concern"})[0] == 200
        assert request(base, "POST", "/api/signals", {"source": "discord", "room": "community", "visibility": "public", "summary": "Export feels slow"})[0] == 200
        assert request(base, "GET", "/api/brief?audience=public")[1]["signal_count"] == 1
        assert request(base, "GET", "/api/brief?audience=private")[1]["signal_count"] == 2
        draft_status, draft = request(base, "POST", "/api/replies", {"topic_key": "export-slow", "draft": "We are investigating this now.", "target_room": "community", "agent": "pulse-community"})
        assert draft_status == 200
        assert request(base, "POST", f"/api/replies/{draft['replies'][-1]['reply_id']}/approve", {"audience": "private"})[0] == 200
        assert len(request(base, "GET", "/api/outbox")[1]["replies"]) == 1
        assert request(base, "GET", "/api/outbox")[1]["replies"][0]["agent"] == "pulse-community"
        assert request(base, "POST", f"/api/outbox/{draft['replies'][-1]['reply_id']}/delivered", {"publisher": "test-publisher"})[0] == 200
        assert len(request(base, "GET", "/api/outbox")[1]["replies"]) == 0
    finally:
        process.terminate()
        process.wait(timeout=3)
