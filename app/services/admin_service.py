"""Administrator actions: managing taxis, rank agents, and terminals."""
from __future__ import annotations

from typing import List

from app.models import (
    Administrator,
    ConflictError,
    RankAgent,
    Taxi,
    TaxiStatus,
    Terminal,
    TrafficLevel,
)
from app.services.lookups import get_rank_agent_or_404, get_taxi_or_404, get_terminal_or_404
from app.store import Store


def add_taxi(store: Store, badge_number: str, driver_name: str) -> Taxi:
    with store.lock:
        if badge_number in store.taxis:
            raise ConflictError(f"Taxi with badge number '{badge_number}' already exists")
        taxi = Taxi(badge_number=badge_number, driver_name=driver_name)
        store.taxis[badge_number] = taxi
        return taxi


def remove_taxi(store: Store, badge_number: str) -> None:
    with store.lock:
        get_taxi_or_404(store, badge_number)
        if badge_number in store.feeder_park_queue:
            store.feeder_park_queue.remove(badge_number)
        del store.taxis[badge_number]
        store.notifications.pop(badge_number, None)


def list_taxis(store: Store) -> List[Taxi]:
    return list(store.taxis.values())


def add_rank_agent(store: Store, agent_id: str, name: str, terminal_id: str | None = None) -> RankAgent:
    with store.lock:
        if agent_id in store.rank_agents:
            raise ConflictError(f"Rank agent with id '{agent_id}' already exists")
        if terminal_id is not None:
            get_terminal_or_404(store, terminal_id)
        agent = RankAgent(agent_id=agent_id, name=name, terminal_id=terminal_id)
        store.rank_agents[agent_id] = agent
        return agent


def remove_rank_agent(store: Store, agent_id: str) -> None:
    with store.lock:
        get_rank_agent_or_404(store, agent_id)
        del store.rank_agents[agent_id]


def list_rank_agents(store: Store) -> List[RankAgent]:
    return list(store.rank_agents.values())


def add_administrator(store: Store, admin_id: str, name: str) -> Administrator:
    with store.lock:
        if admin_id in store.administrators:
            raise ConflictError(f"Administrator with id '{admin_id}' already exists")
        admin = Administrator(admin_id=admin_id, name=name)
        store.administrators[admin_id] = admin
        return admin


def add_terminal(store: Store, terminal_id: str, name: str) -> Terminal:
    with store.lock:
        if terminal_id in store.terminals:
            raise ConflictError(f"Terminal with id '{terminal_id}' already exists")
        terminal = Terminal(terminal_id=terminal_id, name=name)
        store.terminals[terminal_id] = terminal
        return terminal


def remove_terminal(store: Store, terminal_id: str) -> None:
    with store.lock:
        get_terminal_or_404(store, terminal_id)
        del store.terminals[terminal_id]


def list_terminals(store: Store) -> List[Terminal]:
    return list(store.terminals.values())


def set_traffic_level(store: Store, level: TrafficLevel) -> None:
    with store.lock:
        store.traffic_level = level
