#!/usr/bin/env python3
"""Runs the 24-hour, up-to-10,000-driver feeder park load simulation and
prints a summary report (optionally writing a per-15-minutes CSV time
series for charting).

This drives the app's real service layer (the same functions the HTTP API
calls) through a simulated clock, so it's exercising the actual queueing,
dispatch, fare classification, terminal-capacity, and exemption-return
logic under a realistic-shaped day of demand - not a separate model of it.

Usage:
    python scripts/simulate.py
    python scripts/simulate.py --drivers 2000 --seed 7
    python scripts/simulate.py --drivers 10000 --csv out/timeseries.csv --progress 60
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.simulation.config import SimulationConfig
from app.simulation.engine import run_simulation


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--drivers", type=int, default=10_000, help="Number of drivers to simulate (default: 10000)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed, for reproducible runs (default: 42)")
    parser.add_argument(
        "--terminal-capacity", type=int, default=15, help="Rank capacity applied to every terminal (default: 15)"
    )
    parser.add_argument(
        "--flights-per-hour", type=float, default=55.0, help="Peak flights/hour, 05:00-23:00 (default: 55)"
    )
    parser.add_argument("--csv", type=str, default=None, help="Path to write a per-snapshot CSV time series")
    parser.add_argument(
        "--snapshot-interval", type=int, default=15, help="Minutes between report snapshots (default: 15)"
    )
    parser.add_argument(
        "--progress", type=int, default=0, help="Print progress every N simulated minutes (default: 0 = silent)"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    config = SimulationConfig(
        num_drivers=args.drivers,
        seed=args.seed,
        peak_flights_per_hour=args.flights_per_hour,
        snapshot_interval_minutes=args.snapshot_interval,
    )
    config.terminals = {tid: (name, args.terminal_capacity) for tid, (name, _cap) in config.terminals.items()}

    print(f"Simulating a 24h day with {config.num_drivers:,} drivers (seed={config.seed})...")
    started = time.monotonic()
    result = run_simulation(config, progress_every_minutes=args.progress)
    elapsed = time.monotonic() - started

    print(result.stats.to_summary_text())
    print(f"\n(simulation wall-clock time: {elapsed:.2f}s)")

    if args.csv:
        csv_path = Path(args.csv)
        result.stats.write_snapshots_csv(csv_path, terminal_ids=list(config.terminals.keys()))
        print(f"Time series written to {csv_path}")


if __name__ == "__main__":
    main()
