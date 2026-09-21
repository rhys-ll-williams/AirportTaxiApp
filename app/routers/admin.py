"""Administrator endpoints: add/remove taxis and rank agents, manage
terminals, and set the simulated live traffic conditions.
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Response

from app.deps import store_dependency
from app.schemas import (
    RankAgentCreateRequest,
    RankAgentSummary,
    TaxiCreateRequest,
    TaxiSummary,
    TerminalCreateRequest,
    TerminalSummary,
    TrafficLevelRequest,
)
from app.services import admin_service
from app.store import Store

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/taxis", response_model=TaxiSummary, status_code=201)
def add_taxi(payload: TaxiCreateRequest, store: Store = Depends(store_dependency)) -> TaxiSummary:
    taxi = admin_service.add_taxi(store, payload.badge_number, payload.driver_name)
    return TaxiSummary(
        badge_number=taxi.badge_number,
        driver_name=taxi.driver_name,
        status=taxi.status,
        terminal_id=taxi.terminal_id,
        exemption_type=taxi.exemption_type,
    )


@router.delete("/taxis/{badge_number}", status_code=204)
def remove_taxi(badge_number: str, store: Store = Depends(store_dependency)) -> Response:
    admin_service.remove_taxi(store, badge_number)
    return Response(status_code=204)


@router.get("/taxis", response_model=List[TaxiSummary])
def list_taxis(store: Store = Depends(store_dependency)) -> List[TaxiSummary]:
    return [
        TaxiSummary(
            badge_number=t.badge_number,
            driver_name=t.driver_name,
            status=t.status,
            terminal_id=t.terminal_id,
            exemption_type=t.exemption_type,
        )
        for t in admin_service.list_taxis(store)
    ]


@router.post("/rank-agents", response_model=RankAgentSummary, status_code=201)
def add_rank_agent(payload: RankAgentCreateRequest, store: Store = Depends(store_dependency)) -> RankAgentSummary:
    agent = admin_service.add_rank_agent(store, payload.agent_id, payload.name, payload.terminal_id)
    return RankAgentSummary(agent_id=agent.agent_id, name=agent.name, terminal_id=agent.terminal_id)


@router.delete("/rank-agents/{agent_id}", status_code=204)
def remove_rank_agent(agent_id: str, store: Store = Depends(store_dependency)) -> Response:
    admin_service.remove_rank_agent(store, agent_id)
    return Response(status_code=204)


@router.get("/rank-agents", response_model=List[RankAgentSummary])
def list_rank_agents(store: Store = Depends(store_dependency)) -> List[RankAgentSummary]:
    return [
        RankAgentSummary(agent_id=a.agent_id, name=a.name, terminal_id=a.terminal_id)
        for a in admin_service.list_rank_agents(store)
    ]


@router.post("/terminals", response_model=TerminalSummary, status_code=201)
def add_terminal(payload: TerminalCreateRequest, store: Store = Depends(store_dependency)) -> TerminalSummary:
    terminal = admin_service.add_terminal(store, payload.terminal_id, payload.name)
    return TerminalSummary(terminal_id=terminal.terminal_id, name=terminal.name)


@router.delete("/terminals/{terminal_id}", status_code=204)
def remove_terminal(terminal_id: str, store: Store = Depends(store_dependency)) -> Response:
    admin_service.remove_terminal(store, terminal_id)
    return Response(status_code=204)


@router.get("/terminals", response_model=List[TerminalSummary])
def list_terminals(store: Store = Depends(store_dependency)) -> List[TerminalSummary]:
    return [TerminalSummary(terminal_id=t.terminal_id, name=t.name) for t in admin_service.list_terminals(store)]


@router.put("/traffic-conditions", status_code=204)
def set_traffic_conditions(payload: TrafficLevelRequest, store: Store = Depends(store_dependency)) -> Response:
    admin_service.set_traffic_level(store, payload.level)
    return Response(status_code=204)


@router.get("/traffic-conditions")
def get_traffic_conditions(store: Store = Depends(store_dependency)) -> dict:
    return {"level": store.traffic_level.value}
