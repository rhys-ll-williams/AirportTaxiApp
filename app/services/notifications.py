from __future__ import annotations

from typing import List, Optional

from app.models import Notification
from app.services.ids import new_id
from app.store import Store


def notify(store: Store, badge_number: str, message: str, terminal_id: Optional[str] = None) -> Notification:
    notification = Notification(
        notification_id=new_id("notif"),
        taxi_badge=badge_number,
        message=message,
        terminal_id=terminal_id,
    )
    store.notifications[badge_number].append(notification)
    return notification


def list_notifications(store: Store, badge_number: str) -> List[Notification]:
    return list(store.notifications.get(badge_number, []))


def unread_notifications(store: Store, badge_number: str) -> List[Notification]:
    return [n for n in store.notifications.get(badge_number, []) if not n.read]


def mark_all_read(store: Store, badge_number: str) -> None:
    for n in store.notifications.get(badge_number, []):
        n.read = True
