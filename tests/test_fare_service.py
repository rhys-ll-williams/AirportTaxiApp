from datetime import timedelta

import pytest

from app.config import RETURN_TIME_FLOOR_MINUTES, TRAFFIC_MULTIPLIERS
from app.models import ConflictError, FareClassification, TaxiStatus, TrafficLevel, utcnow
from app.services import admin_service, dispatch_service, fare_service, queue_service
from app.store import Store


def _ready_taxi_at_rank(store: Store, badge="T-1", terminal="T5"):
    admin_service.add_taxi(store, badge, "Driver")
    admin_service.add_terminal(store, terminal, "Terminal 5")
    admin_service.add_rank_agent(store, "RA-1", "Agent", terminal)
    queue_service.join_feeder_park(store, badge)
    dispatch_service.call_next_taxi(store, terminal)
    return badge, terminal


def test_classify_known_local_destination():
    classification, round_trip = fare_service.classify_destination("Kensington")
    assert classification == FareClassification.LOCAL
    assert round_trip == 45


def test_classify_known_fares_fare_destination():
    classification, round_trip = fare_service.classify_destination("Windsor")
    assert classification == FareClassification.FARES_FARE
    assert round_trip == 65


def test_classify_unknown_destination_defaults_standard():
    classification, round_trip = fare_service.classify_destination("Manchester")
    assert classification == FareClassification.STANDARD
    assert round_trip is None


def test_classify_manual_override_wins():
    classification, round_trip = fare_service.classify_destination(
        "Some Village", FareClassification.LOCAL, 40
    )
    assert classification == FareClassification.LOCAL
    assert round_trip == 40


def test_record_fare_requires_taxi_to_be_called(store: Store):
    admin_service.add_taxi(store, "T-1", "Driver")
    admin_service.add_terminal(store, "T5", "Terminal 5")
    admin_service.add_rank_agent(store, "RA-1", "Agent", "T5")

    with pytest.raises(ConflictError):
        fare_service.record_fare(store, "T-1", "Windsor", "RA-1")


def test_complete_standard_fare_rejoins_feeder_park(store: Store):
    badge, terminal = _ready_taxi_at_rank(store)
    fare_service.record_fare(store, badge, "Manchester", "RA-1")
    assert store.taxis[badge].status == TaxiStatus.ON_FARE

    taxi = fare_service.complete_fare(store, badge)

    assert taxi.status == TaxiStatus.IN_FEEDER_PARK
    assert queue_service.queue_position(store, badge) == 1
    assert taxi.exemption_type is None


def test_complete_local_fare_applies_floor_when_estimate_is_shorter(store: Store):
    badge, _ = _ready_taxi_at_rank(store)
    # Hounslow's table estimate (25 min) is below the 60 min local floor.
    fare_service.record_fare(store, badge, "Hounslow", "RA-1")

    taxi = fare_service.complete_fare(store, badge)

    assert taxi.status == TaxiStatus.RETURN_EXEMPT
    assert taxi.exemption_type == FareClassification.LOCAL
    expected_minutes = RETURN_TIME_FLOOR_MINUTES[FareClassification.LOCAL] * TRAFFIC_MULTIPLIERS[TrafficLevel.NORMAL]
    delta = (taxi.return_deadline - utcnow()).total_seconds() / 60
    assert abs(delta - expected_minutes) < 0.1


def test_complete_fares_fare_uses_estimate_when_longer_than_floor(store: Store):
    badge, _ = _ready_taxi_at_rank(store)
    # Manual estimate (120 min) exceeds the fares-fare floor (90 min), so the
    # estimate should win rather than being clamped up to the floor.
    fare_service.record_fare(
        store, badge, "Far Away Town", "RA-1",
        classification_override=FareClassification.FARES_FARE,
        round_trip_override_minutes=120,
    )

    taxi = fare_service.complete_fare(store, badge)

    expected_minutes = 120 * TRAFFIC_MULTIPLIERS[TrafficLevel.NORMAL]
    delta = (taxi.return_deadline - utcnow()).total_seconds() / 60
    assert abs(delta - expected_minutes) < 0.1


def test_return_deadline_never_below_floor_regardless_of_traffic(store: Store):
    store.traffic_level = TrafficLevel.NORMAL
    badge, _ = _ready_taxi_at_rank(store)
    fare_service.record_fare(store, badge, "Kensington", "RA-1")  # local, 45 min estimate < 60 floor
    taxi = fare_service.complete_fare(store, badge)

    minutes_granted = (taxi.return_deadline - utcnow()).total_seconds() / 60
    assert minutes_granted >= RETURN_TIME_FLOOR_MINUTES[FareClassification.LOCAL] - 0.1


def test_heavy_traffic_extends_return_deadline(store: Store):
    store.traffic_level = TrafficLevel.HEAVY
    badge, _ = _ready_taxi_at_rank(store)
    fare_service.record_fare(store, badge, "Kensington", "RA-1")
    taxi = fare_service.complete_fare(store, badge)

    minutes_granted = (taxi.return_deadline - utcnow()).total_seconds() / 60
    floor = RETURN_TIME_FLOOR_MINUTES[FareClassification.LOCAL]
    assert minutes_granted > floor  # extended beyond the bare floor by the traffic multiplier


def test_return_to_terminal_moves_taxi_directly_to_chosen_terminal(store: Store):
    admin_service.add_terminal(store, "T2", "Terminal 2")
    badge, _ = _ready_taxi_at_rank(store)
    fare_service.record_fare(store, badge, "Windsor", "RA-1")
    fare_service.complete_fare(store, badge)

    taxi = fare_service.return_to_terminal(store, badge, "T2")

    assert taxi.status == TaxiStatus.CALLED
    assert taxi.terminal_id == "T2"
    assert taxi.self_checked_in is True
    assert taxi.last_return_on_time is True
    assert taxi.exemption_type is None
    # Self check-in bypasses the central queue entirely.
    assert queue_service.queue_position(store, badge) is None


def test_return_to_terminal_flags_late_return_but_still_allows_it(store: Store):
    admin_service.add_terminal(store, "T2", "Terminal 2")
    badge, _ = _ready_taxi_at_rank(store)
    fare_service.record_fare(store, badge, "Windsor", "RA-1")
    fare_service.complete_fare(store, badge)

    # Simulate the deadline having already passed (e.g. traffic diversion, fuel stop).
    store.taxis[badge].return_deadline = utcnow() - timedelta(minutes=5)

    taxi = fare_service.return_to_terminal(store, badge, "T2")

    assert taxi.status == TaxiStatus.CALLED  # not disqualified for being late
    assert taxi.last_return_on_time is False


def test_return_to_terminal_requires_active_exemption(store: Store):
    admin_service.add_taxi(store, "T-1", "Driver")
    admin_service.add_terminal(store, "T2", "Terminal 2")

    with pytest.raises(ConflictError):
        fare_service.return_to_terminal(store, "T-1", "T2")
