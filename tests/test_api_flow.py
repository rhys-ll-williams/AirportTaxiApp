"""End-to-end tests driving the HTTP API the way the frontend does."""
from datetime import timedelta

from fastapi.testclient import TestClient

from app.models import utcnow
from app.store import get_store


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


def test_admin_terminal_listing_includes_capacity_and_occupancy(client: TestClient):
    resp = client.get("/api/admin/terminals")
    body = resp.json()
    t5 = next(t for t in body if t["terminal_id"] == "T5")
    assert t5["capacity"] == 15
    assert t5["occupancy"] == 0
    assert t5["is_full"] is False


def test_admin_can_create_terminal_with_custom_capacity(client: TestClient):
    resp = client.post("/api/admin/terminals", json={"terminal_id": "T1", "name": "Terminal 1", "capacity": 3})
    assert resp.status_code == 201
    assert resp.json()["capacity"] == 3


def test_return_to_terminal_rejects_a_full_terminal(client: TestClient):
    client.post("/api/admin/terminals", json={"terminal_id": "TX", "name": "Terminal X", "capacity": 1})
    client.post("/api/admin/taxis", json={"badge_number": "FILL-1", "driver_name": "Filler"})
    client.post("/api/driver/taxis/FILL-1/join-feeder-park")
    client.post("/api/rank-agent/terminals/TX/call-next")  # fills TX to capacity

    client.post("/api/admin/taxis", json={"badge_number": "T-1", "driver_name": "Alice"})
    client.post("/api/admin/rank-agents", json={"agent_id": "RA-1", "name": "Bob", "terminal_id": "T5"})
    client.post("/api/driver/taxis/T-1/join-feeder-park")
    client.post("/api/rank-agent/terminals/T5/call-next")
    client.post("/api/rank-agent/taxis/T-1/fare", json={"destination": "Windsor", "rank_agent_id": "RA-1"})
    client.post("/api/driver/taxis/T-1/complete-fare")

    resp = client.post("/api/driver/taxis/T-1/return-to-terminal", json={"terminal_id": "TX"})
    assert resp.status_code == 409
    assert "full" in resp.json()["detail"].lower()


def test_return_to_terminal_with_long_eta_defers_until_near_arrival(client: TestClient):
    client.post("/api/admin/taxis", json={"badge_number": "T-1", "driver_name": "Alice"})
    client.post("/api/admin/rank-agents", json={"agent_id": "RA-1", "name": "Bob", "terminal_id": "T5"})
    client.post("/api/driver/taxis/T-1/join-feeder-park")
    client.post("/api/rank-agent/terminals/T5/call-next")
    client.post("/api/rank-agent/taxis/T-1/fare", json={"destination": "Windsor", "rank_agent_id": "RA-1"})
    client.post("/api/driver/taxis/T-1/complete-fare")

    resp = client.post(
        "/api/driver/taxis/T-1/return-to-terminal", json={"terminal_id": "T2", "eta_minutes": 45}
    )
    body = resp.json()
    assert body["status"] == "return_exempt"  # not added yet, just picked
    assert body["pending_return_terminal_id"] == "T2"
    assert body["pending_return_terminal_name"] == "Terminal 2"
    assert body["minutes_until_added"] > 30

    # Fast-forward the driver's expected arrival to just inside the 5-minute add window.
    store = get_store()
    store.taxis["T-1"].expected_arrival_at = utcnow() + timedelta(minutes=2)

    resp = client.get("/api/driver/taxis/T-1")  # any request runs the promotion tick
    body = resp.json()
    assert body["status"] == "called"
    assert body["terminal_id"] == "T2"
    assert body["self_checked_in"] is True
    assert body["pending_return_terminal_id"] is None
