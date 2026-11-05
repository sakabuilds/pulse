#!/usr/bin/env python3
"""Validate and print PULSE's many-to-many platform routing plan."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

SUPPORTED = {"mattermost", "slack", "discord", "telegram", "teams"}
MODES = {"community", "team", "supervisor"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "path",
        nargs="?",
        default="config/pulse.assignments.yaml",
        help="assignment manifest",
    )
    args = parser.parse_args()

    data = yaml.safe_load(Path(args.path).read_text()) or {}
    if data.get("version") != 1:
        raise SystemExit("assignment manifest must have version: 1")

    agents = data.get("agents", {})
    connections = data.get("connections", {})
    unknown_agents = set(agents) - MODES
    unknown_platforms = {
        platform
        for config in agents.values()
        for platform in config.get("platforms", [])
        if platform not in SUPPORTED
    }
    missing_connections = {
        platform
        for config in agents.values()
        for platform in config.get("platforms", [])
        if platform not in connections
    }
    if unknown_agents:
        raise SystemExit(f"unknown Pulse identities: {sorted(unknown_agents)}")
    if unknown_platforms:
        raise SystemExit(f"unsupported platforms: {sorted(unknown_platforms)}")
    if missing_connections:
        raise SystemExit(f"missing Switch connections: {sorted(missing_connections)}")
    invalid_room_types = {
        mode for mode, config in agents.items()
        if config.get("room_type") not in {"private", "shared"}
    }
    if invalid_room_types:
        raise SystemExit(f"invalid room_type for: {sorted(invalid_room_types)}")
    if "supervisor" in agents and agents["supervisor"].get("room_type") != "private":
        raise SystemExit("supervisor must use room_type: private")

    assignments = [
        (mode, config.get("room_type"), platform, connections[platform])
        for mode, config in agents.items()
        for platform in config.get("platforms", [])
    ]
    print("PULSE platform assignment plan")
    for mode, room_type, platform, connection in assignments:
        print(f"- pulse-{mode} -> {platform} [{room_type}] ({connection})")
    print(f"{len(assignments)} room assignments; {len(agents)} Pulse identities")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

