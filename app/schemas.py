"""Pydantic request/response models for the HTTP API."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models import FareClassification, TaxiStatus, TrafficLevel


# --- Admin: taxis / rank agents / terminals -----------------------------------------

class TaxiCreateRequest(BaseModel):
    badge_number: str = Field(..., min_length=1)
    driver_name: str = Field(..., min_length=1)


class RankAgentCreateRequest(BaseModel):
    agent_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    terminal_id: Optional[str] = None


class TerminalCreateRequest(BaseModel):
    terminal_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)


class TrafficLevelRequest(BaseModel):
    level: TrafficLevel


class TaxiSummary(BaseModel):
    badge_number: str
    driver_name: str
    status: TaxiStatus
    terminal_id: Optional[str] = None
    exemption_type: Optional[FareClassification] = None


class RankAgentSummary(BaseModel):
    agent_id: str
    name: str
    terminal_id: Optional[str] = None


class TerminalSummary(BaseModel):
    terminal_id: str
    name: str


# --- Driver-facing status -------------------------------------------------------------

class NotificationOut(BaseModel):
    notification_id: str
    message: str
    terminal_id: Optional[str] = None
    created_at: datetime
    read: bool


class TaxiStatusResponse(BaseModel):
    badge_number: str
    driver_name: str
    status: TaxiStatus

    # Feeder park
    queue_position: Optional[int] = None
    estimated_wait_minutes: Optional[float] = None

    # Terminal assignment
    terminal_id: Optional[str] = None
    terminal_name: Optional[str] = None
    called_at: Optional[datetime] = None
    self_checked_in: bool = False

    # Exemption / return deadline
    exemption_type: Optional[FareClassification] = None
    exemption_destination: Optional[str] = None
    return_deadline: Optional[datetime] = None
    minutes_remaining_to_return: Optional[float] = None
    last_return_on_time: Optional[bool] = None

    notifications: List[NotificationOut] = []


# --- Rank agent actions ---------------------------------------------------------------

class RecordFareRequest(BaseModel):
    destination: str = Field(..., min_length=1)
    rank_agent_id: str = Field(..., min_length=1)
    classification_override: Optional[FareClassification] = None
    round_trip_override_minutes: Optional[float] = Field(default=None, gt=0)


class FareResponse(BaseModel):
    fare_id: str
    taxi_badge: str
    terminal_id: str
    destination: str
    classification: FareClassification
    round_trip_minutes: Optional[float] = None
    recorded_by: str
    recorded_at: datetime
    completed_at: Optional[datetime] = None


class ReturnToTerminalRequest(BaseModel):
    terminal_id: str = Field(..., min_length=1)
    lat: Optional[float] = None
    lon: Optional[float] = None


# --- Feeder park info screens -----------------------------------------------------------

class FeederParkRowOut(BaseModel):
    badge_number: str
    driver_name: str
    position: int
    estimated_wait_minutes: float
    due_soon: bool


class FeederParkScreenResponse(BaseModel):
    due_soon_badge_numbers: List[str]
    lookahead_minutes: int
    queue: List[FeederParkRowOut]
    call_interval_minutes: float
    traffic_level: TrafficLevel


class ErrorResponse(BaseModel):
    detail: str
