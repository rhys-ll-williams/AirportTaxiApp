"""Fare recording, destination classification, and the local/fares-fare
return-exemption lifecycle.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Optional, Tuple

from app.config import RETURN_TIME_FLOOR_MINUTES, TERMINAL_ADD_LEAD_MINUTES, TRAFFIC_MULTIPLIERS
from app.data.destinations import find_destination
from app.models import (
    ConflictError,
    Fare,
    FareClassification,
    Taxi,
    TaxiStatus,
    Terminal,
    utcnow,
)
from app.services.geofence import is_within_airport_geofence
from app.services.ids import new_id
from app.services.lookups import (
    get_rank_agent_or_404,
    get_taxi_or_404,
    get_terminal_or_404,
    terminal_occupancy,
)
from app.services.notifications import notify
from app.store import Store


def classify_destination(
    destination_text: str,
    classification_override: Optional[FareClassification] = None,
    round_trip_override_minutes: Optional[float] = None,
) -> Tuple[FareClassification, Optional[float]]:
    """Classify a destination as STANDARD / LOCAL / FARES_FARE.

    A rank agent's manual override always wins (they know a destination the
    lookup table doesn't, or have better local knowledge). Otherwise we try
    to match the free-text destination against the known destinations table;
    unmatched destinations default to STANDARD (normal rejoin-the-queue
    rules apply) until an agent classifies them explicitly.
    """
    if classification_override is not None:
        return classification_override, round_trip_override_minutes

    match = find_destination(destination_text.strip().lower())
    if match is None:
        return FareClassification.STANDARD, None
    return match.classification, match.typical_round_trip_minutes


def record_fare(
    store: Store,
    badge_number: str,
    destination: str,
    rank_agent_id: str,
    classification_override: Optional[FareClassification] = None,
    round_trip_override_minutes: Optional[float] = None,
) -> Fare:
    """Rank agent input: a passenger at the rank has told the agent where
    they're going, for the taxi currently at the front of that terminal's
    rank (i.e. the taxi the system most recently called or checked in).
    """
    with store.lock:
        taxi = get_taxi_or_404(store, badge_number)
        get_rank_agent_or_404(store, rank_agent_id)
        if taxi.status != TaxiStatus.CALLED or not taxi.terminal_id:
            raise ConflictError(
                f"Taxi {badge_number} is not currently waiting at a terminal rank"
            )
        get_terminal_or_404(store, taxi.terminal_id)

        classification, round_trip = classify_destination(
            destination, classification_override, round_trip_override_minutes
        )

        fare = Fare(
            fare_id=new_id("fare"),
            taxi_badge=badge_number,
            terminal_id=taxi.terminal_id,
            destination=destination,
            classification=classification,
            round_trip_minutes=round_trip,
            recorded_by=rank_agent_id,
        )
        store.fares[fare.fare_id] = fare
        taxi.current_fare_id = fare.fare_id
        taxi.status = TaxiStatus.ON_FARE
        return fare


def _return_deadline_minutes(store: Store, classification: FareClassification, round_trip_minutes: Optional[float]) -> float:
    floor_minutes = RETURN_TIME_FLOOR_MINUTES[classification]
    base_minutes = max(floor_minutes, round_trip_minutes or 0)
    multiplier = TRAFFIC_MULTIPLIERS[store.traffic_level]
    return base_minutes * multiplier


def complete_fare(store: Store, badge_number: str) -> Taxi:
    """Driver marks the fare as complete (passenger dropped off).

    Standard fares rejoin the back of the central feeder park queue
    automatically. Local / Fares Fare exemptions instead start a return
    deadline, after which the driver is free to check back in directly at
    a terminal of their choice.
    """
    with store.lock:
        taxi = get_taxi_or_404(store, badge_number)
        if taxi.status != TaxiStatus.ON_FARE or not taxi.current_fare_id:
            raise ConflictError(f"Taxi {badge_number} does not have a fare in progress")

        fare = store.fares[taxi.current_fare_id]
        fare.completed_at = utcnow()

        taxi.current_fare_id = None
        taxi.terminal_id = None

        if fare.classification == FareClassification.STANDARD:
            taxi.status = TaxiStatus.IN_FEEDER_PARK
            taxi.feeder_park_joined_at = utcnow()
            taxi.exemption_type = None
            taxi.exemption_destination = None
            taxi.return_deadline = None
            store.feeder_park_queue.append(badge_number)
        else:
            minutes = _return_deadline_minutes(store, fare.classification, fare.round_trip_minutes)
            taxi.status = TaxiStatus.RETURN_EXEMPT
            taxi.exemption_type = fare.classification
            taxi.exemption_destination = fare.destination
            taxi.return_deadline = utcnow() + timedelta(minutes=minutes)

        return taxi


def _add_taxi_to_terminal(
    store: Store,
    taxi: Taxi,
    terminal: Terminal,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
) -> None:
    """Actually seats the taxi at the terminal's rank: from this point it
    counts against the terminal's capacity and is visible to rank agents.
    """
    on_time = taxi.return_deadline is None or utcnow() <= taxi.return_deadline
    within_geofence: Optional[bool] = None
    if lat is not None and lon is not None:
        within_geofence = is_within_airport_geofence(lat, lon)

    taxi.status = TaxiStatus.CALLED
    taxi.terminal_id = terminal.terminal_id
    taxi.called_at = utcnow()
    taxi.self_checked_in = True
    taxi.last_return_on_time = on_time
    taxi.exemption_type = None
    taxi.exemption_destination = None
    taxi.return_deadline = None
    taxi.pending_return_terminal_id = None
    taxi.expected_arrival_at = None

    suffix = "" if on_time else " (after the return time limit)"
    geofence_note = ""
    if within_geofence is False:
        geofence_note = " Note: check-in location was outside the airport geofence."
    notify(
        store,
        taxi.badge_number,
        f"You've been added to the rank at {terminal.name}{suffix}.{geofence_note}",
        terminal_id=terminal.terminal_id,
    )


def return_to_terminal(
    store: Store,
    badge_number: str,
    terminal_id: str,
    eta_minutes: float = 0,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
) -> Taxi:
    """Driver exercising a local/fares-fare exemption picks a terminal to
    return to. Any terminal that currently has room can be picked, but the
    driver only actually occupies a rank slot (and becomes visible to rank
    agents) once they're within TERMINAL_ADD_LEAD_MINUTES of arriving - if
    they're picking further out than that, they're recorded as a pending
    return and get added automatically as that window approaches (see
    `promote_due_returns`).
    """
    with store.lock:
        taxi = get_taxi_or_404(store, badge_number)
        if taxi.status != TaxiStatus.RETURN_EXEMPT:
            raise ConflictError(f"Taxi {badge_number} does not have an active return exemption")
        terminal = get_terminal_or_404(store, terminal_id)

        if terminal_occupancy(store, terminal_id) >= terminal.capacity:
            raise ConflictError(
                f"{terminal.name} is full ({terminal.capacity} taxis) - choose a different terminal"
            )

        if eta_minutes <= TERMINAL_ADD_LEAD_MINUTES:
            _add_taxi_to_terminal(store, taxi, terminal, lat, lon)
        else:
            taxi.pending_return_terminal_id = terminal_id
            taxi.expected_arrival_at = utcnow() + timedelta(minutes=eta_minutes)

        return taxi


def promote_due_returns(store: Store) -> None:
    """Adds pending returning drivers to their chosen terminal once they're
    within the lead-time window and a rank slot is actually free. Called
    opportunistically on read/write so state stays fresh without a
    background scheduler.
    """
    with store.lock:
        now = utcnow()
        for taxi in store.taxis.values():
            if taxi.status != TaxiStatus.RETURN_EXEMPT or not taxi.pending_return_terminal_id:
                continue
            if taxi.expected_arrival_at is None:
                continue
            if now < taxi.expected_arrival_at - timedelta(minutes=TERMINAL_ADD_LEAD_MINUTES):
                continue

            terminal = store.terminals.get(taxi.pending_return_terminal_id)
            if terminal is None:
                # Terminal was removed while this return was pending; the
                # driver will need to pick a different one.
                taxi.pending_return_terminal_id = None
                taxi.expected_arrival_at = None
                continue

            if terminal_occupancy(store, terminal.terminal_id) >= terminal.capacity:
                continue  # still full - try again next tick

            _add_taxi_to_terminal(store, taxi, terminal)
