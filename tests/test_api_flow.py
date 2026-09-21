"""End-to-end tests driving the HTTP API the way the frontend does."""
from fastapi.testclient import TestClient


def test_terminals_are_seeded_on_startup(client: TestClient):
    resp = client.get("/api/admin/terminals")
    assert resp.status_code == 200
    ids = {t["terminal_id"] for t in resp.json()}
    assert {"T2", "T3", "T4", "T5"}.issubset(ids)


def test_unknown_taxi_returns_404(client: TestClient):
    resp = client.get("/api/driver/taxis/nope")
    assert resp.status_code == 404


def test_full_standard_fare_lifecycle(client: TestClient):
    client.post("/api/admin/taxis", json={"badge_number": "T-1", "driver_name": "Alice"})
    client.post("/api/admin/rank-agents", json={"agent_id": "RA-1", "name": "Bob", "terminal_id": "T5"})

    resp = client.post("/api/driver/taxis/T-1/join-feeder-park")
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_feeder_park"
    assert resp.json()["queue_position"] == 1

    resp = client.post("/api/rank-agent/terminals/T5/call-next")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "called"
    assert body["terminal_id"] == "T5"
    assert len(body["notifications"]) == 1

    resp = client.post(
        "/api/rank-agent/taxis/T-1/fare",
        json={"destination": "Manchester", "rank_agent_id": "RA-1"},
    )
    assert resp.status_code == 200
    assert resp.json()["classification"] == "standard"

    resp = client.post("/api/driver/taxis/T-1/complete-fare")
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_feeder_park"
    assert resp.json()["queue_position"] == 1


def test_fares_fare_exemption_lifecycle(client: TestClient):
    client.post("/api/admin/taxis", json={"badge_number": "T-1", "driver_name": "Alice"})
    client.post("/api/admin/rank-agents", json={"agent_id": "RA-1", "name": "Bob", "terminal_id": "T5"})
    client.post("/api/driver/taxis/T-1/join-feeder-park")
    client.post("/api/rank-agent/terminals/T5/call-next")

    resp = client.post(
        "/api/rank-agent/taxis/T-1/fare",
        json={"destination": "Windsor", "rank_agent_id": "RA-1"},
    )
    assert resp.json()["classification"] == "fares_fare"

    resp = client.post("/api/driver/taxis/T-1/complete-fare")
    body = resp.json()
    assert body["status"] == "return_exempt"
    assert body["exemption_type"] == "fares_fare"
    assert body["minutes_remaining_to_return"] >= 90 - 0.1

    resp = client.post("/api/driver/taxis/T-1/return-to-terminal", json={"terminal_id": "T2"})
    body = resp.json()
    assert body["status"] == "called"
    assert body["terminal_id"] == "T2"
    assert body["self_checked_in"] is True
    assert body["queue_position"] is None


def test_call_next_on_empty_queue_returns_409(client: TestClient):
    resp = client.post("/api/rank-agent/terminals/T5/call-next")
    assert resp.status_code == 409


def test_feeder_park_screen_reflects_queue(client: TestClient):
    client.post("/api/admin/taxis", json={"badge_number": "T-1", "driver_name": "Alice"})
    client.post("/api/driver/taxis/T-1/join-feeder-park")

    resp = client.get("/api/screens/feeder-park")
    assert resp.status_code == 200
    body = resp.json()
    assert body["queue"][0]["badge_number"] == "T-1"
    assert "T-1" in body["due_soon_badge_numbers"]


def test_admin_can_add_and_remove_taxi(client: TestClient):
    resp = client.post("/api/admin/taxis", json={"badge_number": "T-9", "driver_name": "Zoe"})
    assert resp.status_code == 201

    resp = client.delete("/api/admin/taxis/T-9")
    assert resp.status_code == 204

    resp = client.get("/api/driver/taxis/T-9")
    assert resp.status_code == 404


def test_traffic_conditions_extend_return_deadline(client: TestClient):
    client.post("/api/admin/taxis", json={"badge_number": "T-1", "driver_name": "Alice"})
    client.post("/api/admin/rank-agents", json={"agent_id": "RA-1", "name": "Bob", "terminal_id": "T5"})
    client.put("/api/admin/traffic-conditions", json={"level": "heavy"})

    client.post("/api/driver/taxis/T-1/join-feeder-park")
    client.post("/api/rank-agent/terminals/T5/call-next")
    client.post("/api/rank-agent/taxis/T-1/fare", json={"destination": "Kensington", "rank_agent_id": "RA-1"})
    resp = client.post("/api/driver/taxis/T-1/complete-fare")

    minutes = resp.json()["minutes_remaining_to_return"]
    assert minutes > 60  # local floor is 60 min; heavy traffic should push it higher
