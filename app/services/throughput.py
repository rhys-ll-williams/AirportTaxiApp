"""Estimates how fast taxis are currently being called forward from the
feeder park, based on recent dispatch history, so wait times can be
projected from a driver's queue position.
"""
from __future__ import annotations

from datetime import timedelta
from typing import List

from app.config import (
    DEFAULT_CALL_INTERVAL_MINUTES,
    MIN_CALL_INTERVAL_MINUTES,
    MIN_EVENTS_FOR_ESTIMATE,
    THROUGHPUT_WINDOW_MINUTES,
)
from app.models import DispatchEvent, utcnow
from app.store import Store


def record_dispatch(store: Store, terminal_id: str) -> None:
    store.dispatch_events.append(DispatchEvent(terminal_id=terminal_id))


def current_call_interval_minutes(store: Store) -> float:
    """Average minutes between taxis being called forward, across all
    terminals combined (they all draw from the single central queue).
    Falls back to a sane default until enough history has built up.
    """
    now = utcnow()
    window_start = now - timedelta(minutes=THROUGHPUT_WINDOW_MINUTES)
    recent: List[DispatchEvent] = [e for e in store.dispatch_events if e.at >= window_start]

    if len(recent) < MIN_EVENTS_FOR_ESTIMATE:
        return DEFAULT_CALL_INTERVAL_MINUTES

    timestamps = sorted(e.at for e in recent)
    span_minutes = (timestamps[-1] - timestamps[0]).total_seconds() / 60
    if span_minutes <= 0:
        return DEFAULT_CALL_INTERVAL_MINUTES

    interval = span_minutes / (len(timestamps) - 1)
    return max(interval, MIN_CALL_INTERVAL_MINUTES)
