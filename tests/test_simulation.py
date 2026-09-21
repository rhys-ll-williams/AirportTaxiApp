"""Fast smoke tests for the load simulation - a small driver count so this
stays quick, but exercising the exact same engine/service-layer path as a
full 10,000-driver run (see scripts/simulate.py for that).
"""
from app.config import DEFAULT_TERMINAL_CAPACITY
from app.models import FareClassification
from app.simulation.config import SimulationConfig
from app.simulation.engine import run_simulation
from app.simulation.fares import SimulatedFare, probability_of_not_returning


def _small_config(**overrides) -> SimulationConfig:
    config = SimulationConfig(num_drivers=150, seed=123)
    for key, value in overrides.items():
        setattr(config, key, value)
    return config


def test_simulation_accounts_for_every_driver():
    result = run_simulation(_small_config())
    assert sum(result.stats.final_status_counts.values()) == 150


def test_simulation_leaves_no_taxi_stuck_mid_fare():
    result = run_simulation(_small_config())
    assert result.stats.final_status_counts.get("on_fare", 0) == 0


def test_fares_by_classification_matches_completed_total():
    result = run_simulation(_small_config())
    assert sum(result.stats.fares_by_classification.values()) == result.stats.completed_fares


def test_exemption_outcomes_match_exempt_fare_count():
    result = run_simulation(_small_config())
    exempt_fares = result.stats.fares_by_classification.get(
        "local", 0
    ) + result.stats.fares_by_classification.get("fares_fare", 0)
    outcomes = result.stats.returned_count + result.stats.not_returned_total()
    assert outcomes == exempt_fares


def test_terminal_occupancy_never_exceeds_capacity_under_load():
    result = run_simulation(_small_config(num_drivers=400))
    for snapshot in result.stats.snapshots:
        for terminal_id, occupancy in snapshot.terminal_occupancy.items():
            assert occupancy <= DEFAULT_TERMINAL_CAPACITY, (
                f"terminal {terminal_id} over capacity at minute {snapshot.minute}: {occupancy}"
            )


def test_not_return_probability_is_biased_against_central_london():
    config = SimulationConfig()
    central_fare = SimulatedFare("central london", FareClassification.LOCAL, 55)
    suburban_fare = SimulatedFare("hounslow", FareClassification.LOCAL, 25)

    # Same amount of shift time left, so only the destination differs.
    p_central = probability_of_not_returning(central_fare, config, minutes_left_in_shift=200)
    p_suburban = probability_of_not_returning(suburban_fare, config, minutes_left_in_shift=200)

    assert p_central > p_suburban
    assert p_central == config.base_not_return_rate * config.central_london_not_return_multiplier
    assert p_suburban == config.base_not_return_rate


def test_central_london_fares_decline_more_often_in_simulation():
    # Isolate the destination-driven "declined_*" reasons directly, rather
    # than the raw by-destination tally, which also picks up shift-ended
    # non-returns that have nothing to do with the destination bias.
    result = run_simulation(_small_config(num_drivers=3000))
    declined_central = result.stats.not_returned_by_reason.get("declined_central_london", 0)
    declined_other = result.stats.not_returned_by_reason.get("declined_other", 0)
    assert declined_central > declined_other


def test_simulation_is_deterministic_given_a_seed():
    result_a = run_simulation(_small_config(seed=7))
    result_b = run_simulation(_small_config(seed=7))
    assert result_a.stats.completed_fares == result_b.stats.completed_fares
    assert result_a.stats.fares_by_classification == result_b.stats.fares_by_classification
    assert result_a.stats.not_returned_by_reason == result_b.stats.not_returned_by_reason


def test_run_simulation_does_not_leak_a_simulated_clock():
    from app import clock

    run_simulation(_small_config())
    # After the run, the app's clock must fall back to real wall time again
    # so it doesn't silently affect anything else that imports app.clock.
    assert clock._simulated is None
