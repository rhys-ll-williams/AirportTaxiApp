"""Handles a terminal calling the next available taxi forward."""
from __future__ import annotations

from app.models import ConflictError, Taxi, TaxiStatus
from app.models import utcnow
from app.services import throughput
from app.services.lookups import get_terminal_or_404
from app.services.notifications import notify
from app.store import Store


def call_next_taxi(store: Store, terminal_id: str) -> Taxi:
    """Pop the taxi at the front of the central feeder park queue and send
    it to the requesting terminal, notifying the driver.
    """
    with store.lock:
        terminal = get_terminal_or_404(store, terminal_id)
        if not store.feeder_park_queue:
            raise ConflictError("The feeder park queue is currently empty")

        badge_number = store.feeder_park_queue.pop(0)
        taxi = store.taxis[badge_number]

        taxi.status = TaxiStatus.CALLED
        taxi.terminal_id = terminal_id
        taxi.called_at = utcnow()
        taxi.self_checked_in = False
        taxi.feeder_park_joined_at = None

        throughput.record_dispatch(store, terminal_id)
        notify(
            store,
            badge_number,
            f"You're up! Please proceed to {terminal.name}.",
            terminal_id=terminal_id,
        )
        return taxi
