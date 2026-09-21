"""Domain model: enums and in-memory entities for the taxi rank system."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from app.clock import now as _clock_now


def utcnow() -> datetime:
    return _clock_now()


class TaxiStatus(str, Enum):
    OFFLINE = "offline"
    IN_FEEDER_PARK = "in_feeder_park"
    CALLED = "called"
    ON_FARE = "on_fare"
    RETURN_EXEMPT = "return_exempt"


class FareClassification(str, Enum):
    STANDARD = "standard"
    LOCAL = "local"
    FARES_FARE = "fares_fare"


class TrafficLevel(str, Enum):
    NORMAL = "normal"
    MODERATE = "moderate"
    HEAVY = "heavy"


@dataclass
class Taxi:
    badge_number: str
    driver_name: str
    status: TaxiStatus = TaxiStatus.OFFLINE

    # Feeder park state
    feeder_park_joined_at: Optional[datetime] = None

    # Terminal assignment (CALLED / ON_FARE)
    terminal_id: Optional[str] = None
    called_at: Optional[datetime] = None
    self_checked_in: bool = False

    # Active fare
    current_fare_id: Optional[str] = None

    # Exemption (RETURN_EXEMPT)
    exemption_type: Optional[FareClassification] = None
    exemption_destination: Optional[str] = None
    return_deadline: Optional[datetime] = None
    last_return_on_time: Optional[bool] = None

    # Pending return: a terminal the driver has chosen to head back to while
    # still out on an exemption, but hasn't been added to yet (see
    # TERMINAL_ADD_LEAD_MINUTES). Cleared once promoted to CALLED.
    pending_return_terminal_id: Optional[str] = None
    expected_arrival_at: Optional[datetime] = None

    created_at: datetime = field(default_factory=utcnow)


@dataclass
class Terminal:
    terminal_id: str
    name: str
    capacity: int


@dataclass
class RankAgent:
    agent_id: str
    name: str
    terminal_id: Optional[str] = None


@dataclass
class Administrator:
    admin_id: str
    name: str


@dataclass
class Fare:
    fare_id: str
    taxi_badge: str
    terminal_id: str
    destination: str
    classification: FareClassification
    round_trip_minutes: Optional[float]
    recorded_by: str
    recorded_at: datetime = field(default_factory=utcnow)
    completed_at: Optional[datetime] = None


@dataclass
class Notification:
    notification_id: str
    taxi_badge: str
    message: str
    terminal_id: Optional[str]
    created_at: datetime = field(default_factory=utcnow)
    read: bool = False


@dataclass
class DispatchEvent:
    terminal_id: str
    at: datetime = field(default_factory=utcnow)


class NotFoundError(Exception):
    """Raised when a referenced entity (taxi, terminal, agent...) doesn't exist."""


class ConflictError(Exception):
    """Raised when an action is invalid given the entity's current state."""
