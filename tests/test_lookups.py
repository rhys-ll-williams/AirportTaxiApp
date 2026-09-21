from app.services import admin_service, dispatch_service, queue_service
from app.services.lookups import terminal_has_capacity, terminal_occupancy
from app.store import Store


def test_terminal_occupancy_counts_only_called_taxis_at_that_terminal(store: Store):
    admin_service.add_terminal(store, "T5", "Terminal 5")
    admin_service.add_terminal(store, "T2", "Terminal 2")
    admin_service.add_taxi(store, "T-1", "Alice")
    admin_service.add_taxi(store, "T-2", "Bob")

    queue_service.join_feeder_park(store, "T-1")
    queue_service.join_feeder_park(store, "T-2")
    dispatch_service.call_next_taxi(store, "T5")  # T-1 -> CALLED at T5
    dispatch_service.call_next_taxi(store, "T2")  # T-2 -> CALLED at T2

    assert terminal_occupancy(store, "T5") == 1
    assert terminal_occupancy(store, "T2") == 1


def test_terminal_has_capacity(store: Store):
    terminal = admin_service.add_terminal(store, "T5", "Terminal 5", capacity=1)
    admin_service.add_taxi(store, "T-1", "Alice")
    queue_service.join_feeder_park(store, "T-1")

    assert terminal_has_capacity(store, terminal) is True

    dispatch_service.call_next_taxi(store, "T5")
    assert terminal_has_capacity(store, terminal) is False
