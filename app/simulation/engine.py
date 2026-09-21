"""Runs a full simulated day against the app's real service layer.

This drives exactly the same functions the HTTP API uses (admin_service,
queue_service, dispatch_service, fare_service) through a controllable
clock (app.clock), so the simulation is a genuine load test of the app's
actual queueing, dispatch, classification, capacity, and exemption logic -
not a separate reimplementation of it.

The simulated day is processed minute-by-minute (a "bucket queue"): every
event (a shift starting, a passenger wanting a taxi, a fare finishing, a
pending return coming due) is filed into the bucket for the simulated
minute it happens at, and the loop advances the clock one minute at a time
processing whatever bucket. This keeps a 10,000-driver, 24-hour run to a
few seconds of Python-side work, independent of real wall-clock time.

Rank agents serve whichever taxi has been waiting longest at their
terminal - which, in this simulation, is always a self-checked-in
exemption return (a freshly central-dispatched taxi is matched to the
same demand event that called it forward, so it's never left idle). Only
once no taxi is already waiting does a rank agent call the next one
forward from the central feeder park. `terminal_waiting` tracks that
per-terminal FIFO explicitly so this never needs an O(taxis) scan.
"""
from __future__ import annotations

import random
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import timedelta
from typing import Deque, Dict, List, Tuple

from app import clock
from app.config import TERMINAL_ADD_LEAD_MINUTES
from app.models import ConflictError, TaxiStatus
from app.services import admin_service, dispatch_service, fare_service, queue_service
from app.services.lookups import terminal_occupancy
from app.simulation.config import SimulationConfig
from app.simulation.fares import (
    SimulatedFare,
    one_way_minutes,
    pick_fare,
    probability_of_not_returning,
    return_leg_minutes,
)
from app.simulation.flights import generate_taxi_demand
from app.simulation.population import DriverProfile, generate_driver_population
from app.simulation.report import Snapshot, SimulationStats
from app.store import Store, reset_store

MAX_RETURN_RETRIES = 8
RETRY_DELAY_MINUTES = 5


@dataclass
class SimulationResult:
    stats: SimulationStats
    store: Store
    drivers: List[DriverProfile]


def run_simulation(config: SimulationConfig, progress_every_minutes: int = 0) -> SimulationResult:
    rng = random.Random(config.seed)
    store = reset_store()
    clock.reset()
    clock.set_time(config.day_start)

    for terminal_id, (name, capacity) in config.terminals.items():
        admin_service.add_terminal(store, terminal_id, name, capacity)

    rank_agent_by_terminal: Dict[str, str] = {}
    for terminal_id in config.terminals:
        agent_id = f"SIM-{terminal_id}"
        admin_service.add_rank_agent(store, agent_id, f"Sim Agent {terminal_id}", terminal_id)
        rank_agent_by_terminal[terminal_id] = agent_id

    drivers = generate_driver_population(config)
    driver_by_badge = {d.badge_number: d for d in drivers}
    for d in drivers:
        admin_service.add_taxi(store, d.badge_number, f"Driver {d.badge_number}")

    demand_events, total_flights = generate_taxi_demand(config, rng)

    total_buckets = config.total_buckets
    shift_start_buckets: List[List[str]] = [[] for _ in range(total_buckets)]
    shift_end_buckets: List[List[str]] = [[] for _ in range(total_buckets)]
    for d in drivers:
        shift_start_buckets[min(d.shift_start_minute, total_buckets - 1)].append(d.badge_number)
        shift_end_buckets[min(d.shift_end_minute, total_buckets - 1)].append(d.badge_number)

    demand_buckets: List[List[str]] = [[] for _ in range(total_buckets)]
    for ev in demand_events:
        demand_buckets[min(ev.ready_minute, total_buckets - 1)].append(ev.terminal_id)

    fare_complete_buckets: List[List[Tuple[str, SimulatedFare]]] = [[] for _ in range(total_buckets)]
    # Badges explicitly due for a promotion check at this minute (either
    # their initial due time, or a retry after finding the terminal full).
    promote_checks: List[List[str]] = [[] for _ in range(total_buckets)]
    retry_counts: Dict[str, int] = {}
    terminal_waiting: Dict[str, Deque[str]] = defaultdict(deque)
    badge_last_destination: Dict[str, str] = {}

    stats = SimulationStats(
        total_drivers=config.num_drivers,
        total_flights=total_flights,
        total_taxi_demand=len(demand_events),
    )
    terminal_ids = list(config.terminals.keys())

    for minute in range(total_buckets):
        clock.set_time(config.day_start + timedelta(minutes=minute))

        if progress_every_minutes and minute % progress_every_minutes == 0:
            print(f"  ... simulated minute {minute}/{total_buckets} ({minute / 60:.1f}h)")

        for badge in shift_start_buckets[minute]:
            try:
                queue_service.join_feeder_park(store, badge)
            except ConflictError:
                pass

        for terminal_id in demand_buckets[minute]:
            waiting = terminal_waiting.get(terminal_id)
            taxi = None
            if waiting:
                taxi = store.taxis.get(waiting.popleft())
            if taxi is None:
                try:
                    taxi = dispatch_service.call_next_taxi(store, terminal_id)
                except ConflictError:
                    stats.unmet_demand += 1
                    continue

            fare_choice = pick_fare(config, rng)
            agent_id = rank_agent_by_terminal[terminal_id]
            fare_service.record_fare(store, taxi.badge_number, fare_choice.destination, agent_id)
            stats.fares_by_classification[fare_choice.classification.value] += 1
            badge_last_destination[taxi.badge_number] = fare_choice.destination

            leg = one_way_minutes(fare_choice, config, rng)
            complete_minute = min(minute + max(1, round(leg)), total_buckets - 1)
            fare_complete_buckets[complete_minute].append((taxi.badge_number, fare_choice))

        for badge, fare_choice in fare_complete_buckets[minute]:
            taxi = store.taxis.get(badge)
            if taxi is None or taxi.status != TaxiStatus.ON_FARE:
                continue

            fare_service.complete_fare(store, badge)
            stats.completed_fares += 1
            driver = driver_by_badge[badge]
            taxi = store.taxis[badge]

            if taxi.status == TaxiStatus.IN_FEEDER_PARK:
                if minute >= driver.shift_end_minute:
                    queue_service.leave_feeder_park(store, badge)
                    driver.finished = True
                continue

            if taxi.status != TaxiStatus.RETURN_EXEMPT:
                continue

            minutes_left = driver.shift_end_minute - minute
            shift_over = minutes_left <= 0
            p_not_return = probability_of_not_returning(fare_choice, config, minutes_left)

            if shift_over or rng.random() < p_not_return:
                driver.finished = True
                if shift_over:
                    reason = "shift_ended"
                elif fare_choice.destination in config.central_london_destinations:
                    reason = "declined_central_london"
                else:
                    reason = "declined_other"
                stats.not_returned_by_reason[reason] += 1
                stats.not_returned_by_destination[fare_choice.destination] += 1
                continue

            eta = return_leg_minutes(fare_choice, config, rng)
            candidates = terminal_ids[:]
            rng.shuffle(candidates)
            added_terminal_id = None
            for terminal_id in candidates:
                try:
                    fare_service.return_to_terminal(store, badge, terminal_id, eta_minutes=eta)
                    added_terminal_id = terminal_id
                    break
                except ConflictError:
                    stats.terminal_full_rejections += 1

            if added_terminal_id is None:
                driver.finished = True
                stats.not_returned_by_reason["all_terminals_full"] += 1
                stats.not_returned_by_destination[fare_choice.destination] += 1
                continue

            stats.returned_count += 1
            taxi = store.taxis[badge]
            if taxi.status == TaxiStatus.CALLED:
                terminal_waiting[added_terminal_id].append(badge)
            else:
                due_minute = min(max(minute, round(minute + eta - TERMINAL_ADD_LEAD_MINUTES)), total_buckets - 1)
                promote_checks[due_minute].append(badge)

        if promote_checks[minute]:
            # Any taxi pending a return - not just the ones due this exact
            # minute - might get swept up by this call, so track all of
            # them to notice anyone newly seated and queue them for demand.
            pending_before = {
                t.badge_number: t.pending_return_terminal_id
                for t in store.taxis.values()
                if t.status == TaxiStatus.RETURN_EXEMPT and t.pending_return_terminal_id
            }
            fare_service.promote_due_returns(store)
            for badge, intended_terminal in pending_before.items():
                taxi = store.taxis.get(badge)
                if taxi is not None and taxi.status == TaxiStatus.CALLED:
                    terminal_waiting[intended_terminal].append(badge)

            for badge in promote_checks[minute]:
                taxi = store.taxis.get(badge)
                if taxi is None or taxi.status != TaxiStatus.RETURN_EXEMPT or not taxi.pending_return_terminal_id:
                    continue  # already promoted (possibly just above)
                retries = retry_counts.get(badge, 0)
                if retries < MAX_RETURN_RETRIES:
                    retry_counts[badge] = retries + 1
                    promote_checks[min(minute + RETRY_DELAY_MINUTES, total_buckets - 1)].append(badge)
                else:
                    driver_by_badge[badge].finished = True
                    stats.not_returned_by_reason["terminal_never_freed_up"] += 1
                    stats.not_returned_by_destination[badge_last_destination.get(badge, "unknown")] += 1

        for badge in shift_end_buckets[minute]:
            taxi = store.taxis.get(badge)
            if taxi and taxi.status == TaxiStatus.IN_FEEDER_PARK:
                queue_service.leave_feeder_park(store, badge)
                driver_by_badge[badge].finished = True

        if minute % config.snapshot_interval_minutes == 0 or minute == total_buckets - 1:
            occupancy = {t: terminal_occupancy(store, t) for t in terminal_ids}
            active = sum(
                1
                for t in store.taxis.values()
                if t.status
                in (TaxiStatus.IN_FEEDER_PARK, TaxiStatus.CALLED, TaxiStatus.ON_FARE, TaxiStatus.RETURN_EXEMPT)
            )
            stats.snapshots.append(
                Snapshot(
                    minute=minute,
                    feeder_park_length=len(store.feeder_park_queue),
                    active_drivers=active,
                    terminal_occupancy=occupancy,
                    cumulative_fares=stats.completed_fares,
                )
            )

    for taxi in store.taxis.values():
        stats.final_status_counts[taxi.status.value] += 1

    clock.reset()
    return SimulationResult(stats=stats, store=store, drivers=drivers)
