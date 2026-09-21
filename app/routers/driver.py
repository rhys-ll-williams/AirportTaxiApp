"""Driver-facing endpoints: join the feeder park, check status/notifications,
complete a fare, and (for exempt drivers) check back in at a terminal.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import store_dependency
from app.schemas import ReturnToTerminalRequest, TaxiStatusResponse
from app.serializers import taxi_to_status_response
from app.services import fare_service, queue_service
from app.services.lookups import get_taxi_or_404
from app.services.notifications import mark_all_read
from app.store import Store

router = APIRouter(prefix="/api/driver", tags=["driver"])


@router.get("/taxis/{badge_number}", response_model=TaxiStatusResponse)
def get_status(badge_number: str, store: Store = Depends(store_dependency)) -> TaxiStatusResponse:
    taxi = get_taxi_or_404(store, badge_number)
    return taxi_to_status_response(store, taxi)


@router.post("/taxis/{badge_number}/join-feeder-park", response_model=TaxiStatusResponse)
def join_feeder_park(badge_number: str, store: Store = Depends(store_dependency)) -> TaxiStatusResponse:
    queue_service.join_feeder_park(store, badge_number)
    return taxi_to_status_response(store, get_taxi_or_404(store, badge_number))


@router.post("/taxis/{badge_number}/leave-feeder-park", response_model=TaxiStatusResponse)
def leave_feeder_park(badge_number: str, store: Store = Depends(store_dependency)) -> TaxiStatusResponse:
    queue_service.leave_feeder_park(store, badge_number)
    return taxi_to_status_response(store, get_taxi_or_404(store, badge_number))


@router.post("/taxis/{badge_number}/complete-fare", response_model=TaxiStatusResponse)
def complete_fare(badge_number: str, store: Store = Depends(store_dependency)) -> TaxiStatusResponse:
    fare_service.complete_fare(store, badge_number)
    return taxi_to_status_response(store, get_taxi_or_404(store, badge_number))


@router.post("/taxis/{badge_number}/return-to-terminal", response_model=TaxiStatusResponse)
def return_to_terminal(
    badge_number: str,
    payload: ReturnToTerminalRequest,
    store: Store = Depends(store_dependency),
) -> TaxiStatusResponse:
    fare_service.return_to_terminal(store, badge_number, payload.terminal_id, payload.lat, payload.lon)
    return taxi_to_status_response(store, get_taxi_or_404(store, badge_number))


@router.post("/taxis/{badge_number}/notifications/mark-read", response_model=TaxiStatusResponse)
def mark_notifications_read(badge_number: str, store: Store = Depends(store_dependency)) -> TaxiStatusResponse:
    get_taxi_or_404(store, badge_number)
    mark_all_read(store, badge_number)
    return taxi_to_status_response(store, get_taxi_or_404(store, badge_number))
