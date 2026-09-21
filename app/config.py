"""Central configuration and tunable constants for the Heathrow taxi rank MVP.

These values stand in for what would, in a production system, come from
live traffic feeds, historical dispatch analytics, and airport ops data.
"""
from app.models import FareClassification, TrafficLevel

# --- Feeder park throughput / wait-time estimation ---------------------------------
# How far back we look when estimating the current "taxis called per minute" rate.
THROUGHPUT_WINDOW_MINUTES = 30
# Minimum number of recent dispatch events before we trust the measured rate.
MIN_EVENTS_FOR_ESTIMATE = 3
# Cold-start assumption when there isn't enough dispatch history yet: one taxi
# called forward every N minutes across the whole feeder park.
DEFAULT_CALL_INTERVAL_MINUTES = 3.0
# Never estimate a call happening faster than this (keeps the ETA sane).
MIN_CALL_INTERVAL_MINUTES = 0.25

# --- Feeder park information screens ------------------------------------------------
# Drivers whose estimated call time falls within this many minutes are shown
# on the feeder park badge-number display board.
SCREEN_LOOKAHEAD_MINUTES = 5

# --- Exemption return time limits ---------------------------------------------------
# Floors from the spec: never less than these, but can be extended by traffic
# conditions or by the destination's own estimated round-trip time.
RETURN_TIME_FLOOR_MINUTES = {
    FareClassification.LOCAL: 60,
    FareClassification.FARES_FARE: 90,
}

# Simulated "live traffic" multipliers applied on top of the floor/estimate.
# In production this would be swapped for a call to a live traffic API.
TRAFFIC_MULTIPLIERS = {
    TrafficLevel.NORMAL: 1.0,
    TrafficLevel.MODERATE: 1.15,
    TrafficLevel.HEAVY: 1.35,
}

# --- Geofencing -----------------------------------------------------------------------
# Heathrow Airport approximate centre point.
AIRPORT_LATITUDE = 51.4700
AIRPORT_LONGITUDE = -0.4543
# Radius used to confirm a driver has returned to the airport vicinity. This is
# only used to confirm arrival - it never disqualifies a driver for the route
# or roads they chose to get there.
AIRPORT_GEOFENCE_RADIUS_KM = 8.0

# --- Default seed data ---------------------------------------------------------------
DEFAULT_TERMINALS = [
    ("T2", "Terminal 2"),
    ("T3", "Terminal 3"),
    ("T4", "Terminal 4"),
    ("T5", "Terminal 5"),
]
