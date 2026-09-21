"""Destination selection for simulated fares, and the "does the driver
return?" bias model for Local / Fares Fare exemptions.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional

from app.data.destinations import KNOWN_DESTINATIONS
from app.models import FareClassification
from app.simulation.config import SimulationConfig

_LOCAL_DESTINATIONS = [k for k, v in KNOWN_DESTINATIONS.items() if v.classification == FareClassification.LOCAL]
_FARES_FARE_DESTINATIONS = [
    k for k, v in KNOWN_DESTINATIONS.items() if v.classification == FareClassification.FARES_FARE
]
_STANDARD_DESTINATIONS = [
    "Manchester",
    "Birmingham",
    "unlisted nearby address",
    "business park transfer",
    "long-distance transfer",
]


@dataclass
class SimulatedFare:
    destination: str
    classification: FareClassification
    round_trip_minutes: Optional[float]  # None for Standard


def pick_fare(config: SimulationConfig, rng: random.Random) -> SimulatedFare:
    classification_name = rng.choices(
        list(config.fare_mix.keys()), weights=list(config.fare_mix.values()), k=1
    )[0]

    if classification_name == "standard":
        destination = rng.choice(_STANDARD_DESTINATIONS)
        return SimulatedFare(destination, FareClassification.STANDARD, None)

    pool = _LOCAL_DESTINATIONS if classification_name == "local" else _FARES_FARE_DESTINATIONS
    destination = rng.choice(pool)
    info = KNOWN_DESTINATIONS[destination]
    return SimulatedFare(destination, info.classification, info.typical_round_trip_minutes)


def one_way_minutes(fare: SimulatedFare, config: SimulationConfig, rng: random.Random) -> float:
    """How long the outbound leg (rank to destination) takes."""
    if fare.round_trip_minutes is not None:
        return fare.round_trip_minutes / 2.0
    low, high = config.standard_one_way_minutes
    return rng.uniform(low, high)


def return_leg_minutes(fare: SimulatedFare, config: SimulationConfig, rng: random.Random) -> float:
    """How long the return leg (destination back to the airport) takes,
    with jitter representing traffic variability on the way back.
    """
    base = fare.round_trip_minutes / 2.0 if fare.round_trip_minutes is not None else 30.0
    low, high = config.return_leg_jitter
    return base * rng.uniform(low, high)


def probability_of_not_returning(
    fare: SimulatedFare,
    config: SimulationConfig,
    minutes_left_in_shift: float,
) -> float:
    """Chance a driver just doesn't come back after this exempt fare.

    Biased up for central-London destinations (much more competing street
    work there), and further up if the driver's shift is nearly over by
    the time they'd be heading back.
    """
    rate = config.base_not_return_rate
    if fare.destination in config.central_london_destinations:
        rate *= config.central_london_not_return_multiplier
    if minutes_left_in_shift <= config.end_of_shift_not_return_window_minutes:
        rate *= config.end_of_shift_not_return_multiplier
    return min(rate, 0.95)
