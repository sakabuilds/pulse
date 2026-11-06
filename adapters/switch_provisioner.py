"""Hand Pulse's validated room assignments to a Switch provisioner."""

from __future__ import annotations

import json
import os
import urllib.request


def provision_once(control_url: str, switch_url: str) -> int:
    with urllib.request.urlopen(f"{control_url.rstrip('/')}/api/provisioning-plan", timeout=10) as response:
        plan = json.loads(response.read())["plan"]
    ready = [item for item in plan if item["status"] == "ready"]
    for item in ready:
        body = json.dumps(item).encode()
        request = urllib.request.Request(switch_url, data=body, method="POST", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=15) as response:
            if response.status >= 300:
                raise RuntimeError("Switch provisioner rejected a room assignment")
    return len(ready)


if __name__ == "__main__":
    provision_once(os.environ.get("PULSE_CONTROL_URL", "http://127.0.0.1:4173"), os.environ["PULSE_SWITCH_PROVISION_URL"])
