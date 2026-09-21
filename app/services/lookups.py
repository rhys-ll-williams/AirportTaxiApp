"""Shared entity lookup helpers that raise NotFoundError consistently."""
from __future__ import annotations

from app.models import NotFoundError, RankAgent, Taxi, Terminal
from app.store import Store


def get_taxi_or_404(store: Store, badge_number: str) -> Taxi:
    taxi = store.taxis.get(badge_number)
    if taxi is None:
        raise NotFoundError(f"No taxi with badge number '{badge_number}'")
    return taxi


def get_terminal_or_404(store: Store, terminal_id: str) -> Terminal:
    terminal = store.terminals.get(terminal_id)
    if terminal is None:
        raise NotFoundError(f"No terminal with id '{terminal_id}'")
    return terminal


def get_rank_agent_or_404(store: Store, agent_id: str) -> RankAgent:
    agent = store.rank_agents.get(agent_id)
    if agent is None:
        raise NotFoundError(f"No rank agent with id '{agent_id}'")
    return agent
