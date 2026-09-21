"""Rank agent endpoints: call the next taxi forward for a terminal, and
record a passenger's destination for the taxi currently at the rank.
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends

from app.deps import store_dependency
from app.schemas import FareResponse, RecordFareRequest, TaxiStatusResponse
from app.models import TaxiStatus
from app.serializers import taxi_to_status_response
from app.services import dispatch_service, fare_service
from app.store import Store

router = APIRouter(prefix="/api/rank-agent", tags=["rank-agent"])


@router.post("/terminals/{terminal_id}/call-next", response_model=TaxiStatusResponse)
def call_next_taxi(terminal_id: str, store: Store = Depends(store_dependency)) -> TaxiStatusResponse:
    taxi = dispatch_service.call_next_taxi(store, terminal_id)
    return taxi_to_status_response(store, taxi)


@router.post("/taxis/{badge_number}/fare", response_model=FareResponse)
def record_fare(
    badge_number: str,
    payload: RecordFareRequest,
    store: Store = Depends(store_dependency),
) -> FareResponse:
    fare = fare_service.record_fare(
        store,
        badge_number,
        payload.destination,
        payload.rank_agent_id,
        payload.classification_override,
        payload.round_trip_override_minutes,
    )
    return FareResponse(
        fare_id=fare.fare_id,
        taxi_badge=fare.taxi_badge,
        terminal_id=fare.terminal_id,
        destination=fare.destination,
        classification=fare.classification,
        round_trip_minutes=fare.round_trip_minutes,
        recorded_by=fare.recorded_by,
        recorded_at=fare.recorded_at,
        completed_at=fare.completed_at,
    )


@router.get("/terminals/{terminal_id}/rank", response_model=List[TaxiStatusResponse])
def taxis_at_rank(terminal_id: str, store: Store = Depends(store_dependency)) -> List[TaxiStatusResponse]:
    """Taxis currently called to / checked in at this terminal, awaiting a fare."""
    taxis = [t for t in store.taxis.values() if t.terminal_id == terminal_id and t.status == TaxiStatus.CALLED]
    taxis.sort(key=lambda t: t.called_at or t.badge_number)
    return [taxi_to_status_response(store, t) for t in taxis]
