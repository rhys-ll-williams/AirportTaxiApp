"""Feeder park information screen data: which badge numbers will be called
forward in the near future, so waiting drivers know when to get ready.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import SCREEN_LOOKAHEAD_MINUTES
from app.deps import store_dependency
from app.schemas import FeederParkRowOut, FeederParkScreenResponse
from app.services import queue_service, throughput
from app.store import Store

router = APIRouter(prefix="/api/screens", tags=["screens"])


@router.get("/feeder-park", response_model=FeederParkScreenResponse)
def feeder_park_screen(store: Store = Depends(store_dependency)) -> FeederParkScreenResponse:
    rows = queue_service.feeder_park_snapshot(store)
    return FeederParkScreenResponse(
        due_soon_badge_numbers=[r.badge_number for r in rows if r.due_soon],
        lookahead_minutes=SCREEN_LOOKAHEAD_MINUTES,
        queue=[
            FeederParkRowOut(
                badge_number=r.badge_number,
                driver_name=r.driver_name,
                position=r.position,
                estimated_wait_minutes=r.estimated_wait_minutes,
                due_soon=r.due_soon,
            )
            for r in rows
        ],
        call_interval_minutes=round(throughput.current_call_interval_minutes(store), 2),
        traffic_level=store.traffic_level,
    )
