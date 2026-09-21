"""Tunable parameters for the 24-hour feeder park load simulation.

Every number here is a documented modelling assumption, not a fact about
the real airport - the simulation exists to exercise the app's actual
service-layer logic (queueing, dispatch, classification, terminal
capacity, exemption deadlines) under realistic-shaped load, not to be a
precise digital twin of Heathrow. Override any of these via the CLI
(scripts/simulate.py --help) or by constructing a SimulationConfig
directly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple


@dataclass
class SimulationConfig:
    # --- scale ---
    num_drivers: int = 10_000
    seed: Optional[int] = 42

    # --- simulated day ---
    # Simulation runs from `day_start` (midnight) through 24h of demand,
    # with a trailing buffer during which in-flight drivers are allowed to
    # finish their trip/return naturally rather than being cut off at
    # exactly midnight.
    day_start: datetime = field(
        default_factory=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc)
    )
    day_minutes: int = 24 * 60
    buffer_minutes: int = 6 * 60

    # --- terminals (mirrors the real app's default seed + capacity) ---
    terminals: Dict[str, Tuple[str, int]] = field(
        default_factory=lambda: {
            "T2": ("Terminal 2", 15),
            "T3": ("Terminal 3", 15),
            "T4": ("Terminal 4", 15),
            "T5": ("Terminal 5", 15),
        }
    )
    # Relative share of flights routed to each terminal - roughly mirrors
    # Heathrow's actual airline allocation (T5 is BA's home terminal and
    # handles the largest share of movements).
    terminal_flight_weights: Dict[str, float] = field(
        default_factory=lambda: {"T2": 0.25, "T3": 0.25, "T4": 0.15, "T5": 0.35}
    )

    # --- flight / passenger demand ---
    # ~55 flights/hour between 05:00-23:00 as specified; a much lower
    # baseline overnight (Heathrow's night-flight restrictions mean very
    # few scheduled movements between 23:00-05:00, but delayed/diverted
    # arrivals do still happen).
    peak_flights_per_hour: float = 55.0
    overnight_flights_per_hour: float = 3.0
    operating_hours: Tuple[int, int] = (5, 23)  # [start, end)
    # Average number of passengers per flight who go to the taxi rank
    # (a small fraction of a ~150-250 seat aircraft).
    taxi_passengers_per_flight_mean: float = 8.0
    # Minutes between a flight landing and its passengers reaching the
    # rank (deplaning, immigration, baggage reclaim).
    passenger_ready_delay_minutes: Tuple[float, float] = (10.0, 35.0)

    # --- fare mix (must sum to 1.0) ---
    # Share of rank fares that are Standard / Local / Fares Fare. Standard
    # covers both short unlisted local hops and genuine long-distance
    # transfers - i.e. most airport taxi fares in practice.
    fare_mix: Dict[str, float] = field(
        default_factory=lambda: {"standard": 0.55, "local": 0.30, "fares_fare": 0.15}
    )
    # One-way drive time for a Standard fare (no round-trip figure exists
    # for these in the destination table, since the driver doesn't return
    # from them under an exemption).
    standard_one_way_minutes: Tuple[float, float] = (15.0, 60.0)

    # --- driver shift pattern ---
    # A 3-mode mixture of shift start times (hour of day, std dev in
    # hours), loosely tracking the morning/evening flight demand peaks so
    # driver supply roughly follows demand, plus weights for how common
    # each mode is.
    shift_start_modes: Tuple[Tuple[float, float], ...] = (
        (5.5, 1.5),   # early/dawn shift
        (11.0, 2.5),  # day shift
        (17.5, 2.0),  # evening shift
    )
    shift_start_mode_weights: Tuple[float, ...] = (0.35, 0.40, 0.25)
    shift_length_hours: Tuple[float, float] = (8.0, 1.5)  # mean, std dev
    shift_length_bounds_hours: Tuple[float, float] = (4.0, 11.0)

    # --- return-trip timing ---
    # A returning driver's drive-back leg is modelled as roughly half the
    # destination's known round trip, with jitter for traffic variability.
    return_leg_jitter: Tuple[float, float] = (0.85, 1.25)  # multiplier range

    # --- "does the driver return?" bias ---
    # Baseline chance an exempt (Local/Fares Fare) driver simply doesn't
    # come back, before any destination bias is applied.
    base_not_return_rate: float = 0.12
    # Destinations at the centre of London have far more competing street
    # hails and ranks, so a driver dropped there is much more tempted to
    # just keep working independently instead of trekking back to the
    # airport - this multiplies the baseline rate for those destinations.
    central_london_not_return_multiplier: float = 2.5
    central_london_destinations: Tuple[str, ...] = (
        "central london",
        "paddington",
        "kensington",
        "chelsea",
        "victoria",
        "canary wharf",
    )
    # A driver already close to the end of their shift when they'd
    # otherwise return is further biased towards just calling it a day.
    end_of_shift_not_return_window_minutes: float = 45.0
    end_of_shift_not_return_multiplier: float = 1.6

    # --- reporting ---
    snapshot_interval_minutes: int = 15

    @property
    def total_buckets(self) -> int:
        return self.day_minutes + self.buffer_minutes
