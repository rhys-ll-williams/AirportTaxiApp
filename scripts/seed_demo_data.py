"""Populates the running app with sample taxis, rank agents, and a starter
feeder park queue so the UI has something to show immediately.

Usage (with the dev server already running on localhost:8000):
    python scripts/seed_demo_data.py
"""
from __future__ import annotations

import sys
import urllib.error
import urllib.request
import json

BASE_URL = "http://127.0.0.1:8000"

TAXIS = [
    ("T-101", "Alice Ng"),
    ("T-102", "Ben Osei"),
    ("T-103", "Chris Patel"),
    ("T-104", "Dana Williams"),
    ("T-105", "Errol Khan"),
]

RANK_AGENTS = [
    ("RA-T2", "Sam Carter", "T2"),
    ("RA-T5", "Jo Fenwick", "T5"),
]


def post(path: str, payload: dict) -> None:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 409:
            print(f"  (already exists) {path}")
        else:
            raise


def main() -> None:
    print(f"Seeding demo data into {BASE_URL} ...")
    for badge, name in TAXIS:
        post("/api/admin/taxis", {"badge_number": badge, "driver_name": name})
        print(f"  taxi {badge} ({name})")

    for agent_id, name, terminal_id in RANK_AGENTS:
        post("/api/admin/rank-agents", {"agent_id": agent_id, "name": name, "terminal_id": terminal_id})
        print(f"  rank agent {agent_id} ({name}) @ {terminal_id}")

    for badge, _ in TAXIS[:3]:
        post(f"/api/driver/taxis/{badge}/join-feeder-park", {})
        print(f"  {badge} joined the feeder park")

    print("Done. Visit http://127.0.0.1:8000/ to explore the app.")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.URLError as exc:
        print(f"Could not reach {BASE_URL} - is the server running? ({exc})", file=sys.stderr)
        sys.exit(1)
