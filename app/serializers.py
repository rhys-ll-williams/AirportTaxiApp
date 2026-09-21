"""Converts internal dataclasses into API response schemas."""
from __future__ import annotations

from app.models import Taxi, utcnow
from app.schemas import NotificationOut, TaxiStatusResponse
from app.services import queue_service
from app.services.notifications import list_notifications
from app.store import Store


def taxi_to_status_response(store: Store, taxi: Taxi) -> TaxiStatusResponse:
    terminal_name = None
    if taxi.terminal_id and taxi.terminal_id in store.terminals:
        terminal_name = store.terminals[taxi.terminal_id].name

    minutes_remaining = None
    if taxi.return_deadline is not None:
        delta = (taxi.return_deadline - utcnow()).total_seconds() / 60
        minutes_remaining = round(delta, 1)

    notifications = [
        NotificationOut(
            notification_id=n.notification_id,
            message=n.message,
            terminal_id=n.terminal_id,
            created_at=n.created_at,
            read=n.read,
        )
        for n in sorted(list_notifications(store, taxi.badge_number), key=lambda n: n.created_at, reverse=True)
    ]

    return TaxiStatusResponse(
        badge_number=taxi.badge_number,
        driver_name=taxi.driver_name,
        status=taxi.status,
        queue_position=queue_service.queue_position(store, taxi.badge_number),
        estimated_wait_minutes=queue_service.estimate_wait_minutes(store, taxi.badge_number),
        terminal_id=taxi.terminal_id,
        terminal_name=terminal_name,
        called_at=taxi.called_at,
        self_checked_in=taxi.self_checked_in,
        exemption_type=taxi.exemption_type,
        exemption_destination=taxi.exemption_destination,
        return_deadline=taxi.return_deadline,
        minutes_remaining_to_return=minutes_remaining,
        last_return_on_time=taxi.last_return_on_time,
        notifications=notifications,
    )
