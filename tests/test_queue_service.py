from app.config import DEFAULT_CALL_INTERVAL_MINUTES
from app.models import TaxiStatus
from app.services import admin_service, dispatch_service, queue_service
from app.store import Store


def _add_taxi(store: Store, badge: str, name: str = "Driver"):
    admin_service.add_taxi(store, badge, name)


def test_join_feeder_park_sets_status_and_position(store: Store):
    _add_taxi(store, "T-1")
    queue_service.join_feeder_park(store, "T-1")

    taxi = store.taxis["T-1"]
    assert taxi.status == TaxiStatus.IN_FEEDER_PARK
    assert taxi.feeder_park_joined_at is not None
    assert queue_service.queue_position(store, "T-1") == 1


def test_queue_position_is_fifo(store: Store):
    for badge in ("T-1", "T-2", "T-3"):
        _add_taxi(store, badge)
        queue_service.join_feeder_park(store, badge)

    assert queue_service.queue_position(store, "T-1") == 1
    assert queue_service.queue_position(store, "T-2") == 2
    assert queue_service.queue_position(store, "T-3") == 3


def test_estimate_wait_cold_start_uses_default_interval(store: Store):
    for badge in ("T-1", "T-2"):
        _add_taxi(store, badge)
        queue_service.join_feeder_park(store, badge)

    wait = queue_service.estimate_wait_minutes(store, "T-2")
    assert wait == round(2 * DEFAULT_CALL_INTERVAL_MINUTES, 1)


def test_estimate_wait_is_none_when_not_queued(store: Store):
    _add_taxi(store, "T-1")
    assert queue_service.estimate_wait_minutes(store, "T-1") is None


def test_call_next_removes_from_queue_and_shifts_positions(store: Store):
    admin_service.add_terminal(store, "T5", "Terminal 5")
    for badge in ("T-1", "T-2"):
        _add_taxi(store, badge)
        queue_service.join_feeder_park(store, badge)

    dispatch_service.call_next_taxi(store, "T5")

    assert queue_service.queue_position(store, "T-1") is None
    assert queue_service.queue_position(store, "T-2") == 1
    assert store.taxis["T-1"].status == TaxiStatus.CALLED
    assert store.taxis["T-1"].terminal_id == "T5"


def test_feeder_park_snapshot_flags_due_soon(store: Store):
    _add_taxi(store, "T-1")
    queue_service.join_feeder_park(store, "T-1")

    rows = queue_service.feeder_park_snapshot(store)
    assert len(rows) == 1
    assert rows[0].due_soon is True  # 1 * 3min default interval <= 5min lookahead
    assert queue_service.due_soon_badge_numbers(store) == ["T-1"]
