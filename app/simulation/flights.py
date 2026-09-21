"""Generates Heathrow's flight-driven taxi demand for the simulated day.

Flights arrive at ~55/hour between 05:00-23:00 (with a realistic morning
and evening bank of extra arrivals layered on top, averaging out to that
rate across the window) and a much lower baseline overnight. Each flight
sends a handful of taxi-seeking passengers to a rank a little while after
touchdown.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List, Tuple

from app.simulation.config import SimulationConfig


@dataclass
class TaxiDemandEvent:
    ready_minute: int
    terminal_id: str


def _poisson(rng: random.Random, lam: float) -> int:
    if lam <= 0:
        return 0
    limit = math.exp(-lam)
    k = 0
    p = 1.0
    while True:
        k += 1
        p *= rng.random()
        if p <= limit:
            return k - 1


def _bump_shape(hour: float) -> float:
    """Relative flight density: a floor plus a morning and evening bank."""
    morning = math.exp(-0.5 * ((hour - 8.0) / 2.0) ** 2)
    evening = math.exp(-0.5 * ((hour - 18.0) / 2.5) ** 2)
    return 0.4 + morning + 0.8 * evening


def _build_rate_per_minute(config: SimulationConfig) -> List[float]:
    """Per-minute flight arrival rate for the whole day, shaped so the
    average across the operating window matches `peak_flights_per_hour`.
    """
    start_hour, end_hour = config.operating_hours
    window_start = start_hour * 60
    window_end = end_hour * 60

    raw = [0.0] * config.day_minutes
    window_minutes = []
    for m in range(config.day_minutes):
        if window_start <= m < window_end:
            hour = m / 60.0
            raw[m] = _bump_shape(hour)
            window_minutes.append(m)

    mean_raw = (sum(raw[m] for m in window_minutes) / len(window_minutes)) if window_minutes else 1.0
    peak_per_minute = config.peak_flights_per_hour / 60.0
    overnight_per_minute = config.overnight_flights_per_hour / 60.0

    rate = [0.0] * config.day_minutes
    for m in range(config.day_minutes):
        if window_start <= m < window_end:
            rate[m] = peak_per_minute * (raw[m] / mean_raw)
        else:
            rate[m] = overnight_per_minute
    return rate


def generate_taxi_demand(
    config: SimulationConfig, rng: random.Random
) -> Tuple[List[TaxiDemandEvent], int]:
    """Returns (demand events sorted by ready minute, total flight count)."""
    rate_per_minute = _build_rate_per_minute(config)
    terminal_ids = list(config.terminal_flight_weights.keys())
    terminal_weights = [config.terminal_flight_weights[t] for t in terminal_ids]

    events: List[TaxiDemandEvent] = []
    total_flights = 0
    ready_low, ready_high = config.passenger_ready_delay_minutes
    last_minute = config.total_buckets - 1

    for minute in range(config.day_minutes):
        num_flights = _poisson(rng, rate_per_minute[minute])
        for _ in range(num_flights):
            total_flights += 1
            terminal_id = rng.choices(terminal_ids, weights=terminal_weights, k=1)[0]
            num_passengers = _poisson(rng, config.taxi_passengers_per_flight_mean)
            for _ in range(num_passengers):
                delay = rng.uniform(ready_low, ready_high)
                ready_minute = min(int(round(minute + delay)), last_minute)
                events.append(TaxiDemandEvent(ready_minute=ready_minute, terminal_id=terminal_id))

    events.sort(key=lambda e: e.ready_minute)
    return events, total_flights
