"""The central feeder park queue: joining, position, and ETA estimation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from app.config import SCREEN_LOOKAHEAD_MINUTES
from app.models import ConflictError, TaxiStatus, utcnow
from app.services import throughput
from app.services.lookups import get_taxi_or_404
from app.store import Store


def join_feeder_park(store: Store, badge_number: str) -> None:
    with store.lock:
        taxi = get_taxi_or_404(store, badge_number)
        if taxi.status != TaxiStatus.OFFLINE:
            raise ConflictError(
                f"Taxi {badge_number} cannot join the feeder park from status '{taxi.status.value}'"
            )
        taxi.status = TaxiStatus.IN_FEEDER_PARK
        taxi.feeder_park_joined_at = utcnow()
        store.feeder_park_queue.append(badge_number)


def leave_feeder_park(store: Store, badge_number: str) -> None:
    """Driver going offline voluntarily while still waiting in the queue."""
    with store.lock:
        taxi = get_taxi_or_404(store, badge_number)
        if taxi.status != TaxiStatus.IN_FEEDER_PARK:
            raise ConflictError(f"Taxi {badge_number} is not currently in the feeder park")
        if badge_number in store.feeder_park_queue:
            store.feeder_park_queue.remove(badge_number)
        taxi.status = TaxiStatus.OFFLINE
        taxi.feeder_park_joined_at = None


def queue_position(store: Store, badge_number: str) -> Optional[int]:
    """1-indexed position in the feeder park queue, or None if not queued."""
    if badge_number not in store.feeder_park_queue:
        return None
    return store.feeder_park_queue.index(badge_number) + 1


def estimate_wait_minutes(store: Store, badge_number: str) -> Optional[float]:
    position = queue_position(store, badge_number)
    if position is None:
        return None
    interval = throughput.current_call_interval_minutes(store)
    return round(position * interval, 1)


@dataclass
class FeederParkRow:
    badge_number: str
    driver_name: str
    position: int
    estimated_wait_minutes: float
    due_soon: bool


def feeder_park_snapshot(store: Store) -> List[FeederParkRow]:
    interval = throughput.current_call_interval_minutes(store)
    rows: List[FeederParkRow] = []
    for index, badge_number in enumerate(store.feeder_park_queue):
        taxi = store.taxis.get(badge_number)
        if taxi is None:
            continue
        position = index + 1
        wait = round(position * interval, 1)
        rows.append(
            FeederParkRow(
                badge_number=badge_number,
                driver_name=taxi.driver_name,
                position=position,
                estimated_wait_minutes=wait,
                due_soon=wait <= SCREEN_LOOKAHEAD_MINUTES,
            )
        )
    return rows


def due_soon_badge_numbers(store: Store) -> List[str]:
    return [row.badge_number for row in feeder_park_snapshot(store) if row.due_soon]
