"""Generates each driver's badge number and working shift for the day."""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List

from app.simulation.config import SimulationConfig


@dataclass
class DriverProfile:
    badge_number: str
    shift_start_minute: int
    shift_end_minute: int
    finished: bool = False  # set once the driver has no more activity scheduled


def _sample_shift_start_hour(rng: random.Random, config: SimulationConfig) -> float:
    mode_index = rng.choices(
        range(len(config.shift_start_modes)),
        weights=config.shift_start_mode_weights,
        k=1,
    )[0]
    mean_hour, std_hours = config.shift_start_modes[mode_index]
    hour = rng.gauss(mean_hour, std_hours)
    return min(max(hour, 0.0), 23.75)


def generate_driver_population(config: SimulationConfig) -> List[DriverProfile]:
    rng = random.Random(config.seed)
    drivers: List[DriverProfile] = []
    badge_width = max(6, len(str(config.num_drivers)))

    for i in range(config.num_drivers):
        start_hour = _sample_shift_start_hour(rng, config)
        length_mean, length_std = config.shift_length_hours
        low, high = config.shift_length_bounds_hours
        length_hours = min(max(rng.gauss(length_mean, length_std), low), high)

        start_minute = int(round(start_hour * 60))
        end_minute = int(round(start_minute + length_hours * 60))
        end_minute = min(end_minute, config.day_minutes - 1)

        badge = f"D-{i + 1:0{badge_width}d}"
        drivers.append(
            DriverProfile(
                badge_number=badge,
                shift_start_minute=start_minute,
                shift_end_minute=max(end_minute, start_minute + 30),
            )
        )

    return drivers
