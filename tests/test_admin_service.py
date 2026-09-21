import pytest

from app.models import ConflictError, NotFoundError
from app.services import admin_service, queue_service
from app.store import Store


def test_add_and_list_taxi(store: Store):
    admin_service.add_taxi(store, "T-1", "Alice")
    taxis = admin_service.list_taxis(store)
    assert len(taxis) == 1
    assert taxis[0].badge_number == "T-1"


def test_add_duplicate_taxi_conflicts(store: Store):
    admin_service.add_taxi(store, "T-1", "Alice")
    with pytest.raises(ConflictError):
        admin_service.add_taxi(store, "T-1", "Someone Else")


def test_remove_unknown_taxi_raises_not_found(store: Store):
    with pytest.raises(NotFoundError):
        admin_service.remove_taxi(store, "does-not-exist")


def test_remove_taxi_also_removes_it_from_feeder_park_queue(store: Store):
    admin_service.add_taxi(store, "T-1", "Alice")
    queue_service.join_feeder_park(store, "T-1")
    assert queue_service.queue_position(store, "T-1") == 1

    admin_service.remove_taxi(store, "T-1")

    assert "T-1" not in store.taxis
    assert "T-1" not in store.feeder_park_queue


def test_add_rank_agent_requires_valid_terminal(store: Store):
    with pytest.raises(NotFoundError):
        admin_service.add_rank_agent(store, "RA-1", "Bob", "T99")


def test_add_and_remove_rank_agent(store: Store):
    admin_service.add_terminal(store, "T5", "Terminal 5")
    admin_service.add_rank_agent(store, "RA-1", "Bob", "T5")
    assert len(admin_service.list_rank_agents(store)) == 1

    admin_service.remove_rank_agent(store, "RA-1")
    assert admin_service.list_rank_agents(store) == []
