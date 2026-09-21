"""In-memory data store for the MVP.

A single process-wide `Store` instance holds all application state, guarded
by a re-entrant lock so concurrent requests can't corrupt the feeder park
queue. This keeps the MVP dependency-free (no database to stand up) while
keeping all state access behind one object, so swapping in a real database
later only means replacing this module's internals.
"""
from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List

from app.models import (
    Administrator,
    DispatchEvent,
    Fare,
    Notification,
    RankAgent,
    Taxi,
    Terminal,
    TrafficLevel,
)


@dataclass
class Store:
    taxis: Dict[str, Taxi] = field(default_factory=dict)
    terminals: Dict[str, Terminal] = field(default_factory=dict)
    rank_agents: Dict[str, RankAgent] = field(default_factory=dict)
    administrators: Dict[str, Administrator] = field(default_factory=dict)

    feeder_park_queue: List[str] = field(default_factory=list)

    fares: Dict[str, Fare] = field(default_factory=dict)
    notifications: Dict[str, List[Notification]] = field(default_factory=lambda: defaultdict(list))
    dispatch_events: List[DispatchEvent] = field(default_factory=list)

    traffic_level: TrafficLevel = TrafficLevel.NORMAL

    lock: threading.RLock = field(default_factory=threading.RLock)


_store = Store()


def get_store() -> Store:
    return _store


def reset_store() -> Store:
    """Replace global state with a fresh store. Used by tests and demo resets."""
    global _store
    _store = Store()
    return _store
