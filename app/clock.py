"""A controllable clock so the app's business logic can be driven by a
simulated clock instead of real wall time.

Production code is unaffected: by default `now()` returns real UTC time.
The load-test simulation (app/simulation/) calls `set_time`/`advance` to
drive the exact same service-layer functions the HTTP API uses, but across
a simulated 24-hour day in seconds rather than real time.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

_simulated: Optional[datetime] = None


def now() -> datetime:
    if _simulated is not None:
        return _simulated
    return datetime.now(timezone.utc)


def set_time(dt: datetime) -> None:
    global _simulated
    _simulated = dt


def advance(delta: timedelta) -> None:
    global _simulated
    _simulated = now() + delta


def reset() -> None:
    """Return to using real wall-clock time."""
    global _simulated
    _simulated = None
