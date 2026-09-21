"""Geofencing helper used only to confirm a returning driver is back in the
airport vicinity when they check in - never to judge or penalize the route
they took to get there (traffic diversions, a fuel stop, etc. are all fine).
"""
from __future__ import annotations

from math import asin, cos, radians, sin, sqrt
from typing import Optional

from app.config import AIRPORT_GEOFENCE_RADIUS_KM, AIRPORT_LATITUDE, AIRPORT_LONGITUDE

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1_r, lon1_r, lat2_r, lon2_r = map(radians, (lat1, lon1, lat2, lon2))
    d_lat = lat2_r - lat1_r
    d_lon = lon2_r - lon1_r
    a = sin(d_lat / 2) ** 2 + cos(lat1_r) * cos(lat2_r) * sin(d_lon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


def is_within_airport_geofence(
    lat: float,
    lon: float,
    radius_km: float = AIRPORT_GEOFENCE_RADIUS_KM,
) -> bool:
    return haversine_km(lat, lon, AIRPORT_LATITUDE, AIRPORT_LONGITUDE) <= radius_km


def distance_to_airport_km(lat: float, lon: float) -> float:
    return haversine_km(lat, lon, AIRPORT_LATITUDE, AIRPORT_LONGITUDE)
