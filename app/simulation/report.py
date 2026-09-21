"""Stats collection and output formatting for a simulation run."""
from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List


@dataclass
class Snapshot:
    minute: int
    feeder_park_length: int
    active_drivers: int
    terminal_occupancy: Dict[str, int]
    cumulative_fares: int


@dataclass
class SimulationStats:
    total_drivers: int = 0
    total_flights: int = 0
    total_taxi_demand: int = 0
    unmet_demand: int = 0  # passenger wanted a taxi, feeder park was empty

    fares_by_classification: Counter = field(default_factory=Counter)
    completed_fares: int = 0

    returned_count: int = 0
    not_returned_by_reason: Counter = field(default_factory=Counter)
    not_returned_by_destination: Counter = field(default_factory=Counter)
    terminal_full_rejections: int = 0

    snapshots: List[Snapshot] = field(default_factory=list)
    final_status_counts: Counter = field(default_factory=Counter)

    def not_returned_total(self) -> int:
        return sum(self.not_returned_by_reason.values())

    def to_summary_text(self) -> str:
        lines = []
        lines.append("=" * 72)
        lines.append("HEATHROW FEEDER PARK - 24 HOUR SIMULATION SUMMARY")
        lines.append("=" * 72)
        lines.append(f"Drivers simulated:            {self.total_drivers:,}")
        lines.append(f"Flights simulated:             {self.total_flights:,}")
        lines.append(f"Taxi-seeking passengers:      {self.total_taxi_demand:,}")
        lines.append(
            f"  ...unmet (no taxi available): {self.unmet_demand:,} "
            f"({self._pct(self.unmet_demand, self.total_taxi_demand)})"
        )
        lines.append("")
        lines.append("Fares by classification:")
        for classification in ("standard", "local", "fares_fare"):
            count = self.fares_by_classification.get(classification, 0)
            lines.append(f"  {classification:<12} {count:,}")
        lines.append(f"Total fares completed:          {self.completed_fares:,}")
        lines.append("")
        exempt_total = self.returned_count + self.not_returned_total()
        lines.append("Local / Fares Fare exemption outcomes:")
        lines.append(f"  Returned to a terminal:       {self.returned_count:,} ({self._pct(self.returned_count, exempt_total)})")
        lines.append(f"  Did not return:                {self.not_returned_total():,} ({self._pct(self.not_returned_total(), exempt_total)})")
        for reason, count in self.not_returned_by_reason.most_common():
            lines.append(f"    - {reason:<28} {count:,}")
        lines.append("")
        if self.not_returned_by_destination:
            lines.append("Top non-return destinations:")
            for dest, count in self.not_returned_by_destination.most_common(8):
                lines.append(f"  {dest:<20} {count:,}")
            lines.append("")
        lines.append(f"Terminal-full pick rejections:  {self.terminal_full_rejections:,}")
        lines.append("")
        lines.append("Final taxi status at end of simulated day:")
        for status, count in sorted(self.final_status_counts.items()):
            lines.append(f"  {status:<16} {count:,}")
        lines.append("=" * 72)
        return "\n".join(lines)

    @staticmethod
    def _pct(part: int, whole: int) -> str:
        if whole <= 0:
            return "n/a"
        return f"{100.0 * part / whole:.1f}%"

    def write_snapshots_csv(self, path: Path, terminal_ids: List[str]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                ["minute", "hour", "feeder_park_length", "active_drivers", "cumulative_fares"]
                + [f"occupancy_{t}" for t in terminal_ids]
            )
            for snap in self.snapshots:
                writer.writerow(
                    [
                        snap.minute,
                        round(snap.minute / 60.0, 2),
                        snap.feeder_park_length,
                        snap.active_drivers,
                        snap.cumulative_fares,
                    ]
                    + [snap.terminal_occupancy.get(t, 0) for t in terminal_ids]
                )
