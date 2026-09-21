from app.config import AIRPORT_LATITUDE, AIRPORT_LONGITUDE
from app.services.geofence import distance_to_airport_km, haversine_km, is_within_airport_geofence


def test_haversine_zero_distance_for_same_point():
    assert haversine_km(51.5, -0.1, 51.5, -0.1) == 0


def test_haversine_known_distance_roughly_correct():
    # London (~51.5074, -0.1278) to Paris (~48.8566, 2.3522) is ~344km.
    d = haversine_km(51.5074, -0.1278, 48.8566, 2.3522)
    assert 330 < d < 360


def test_airport_centre_is_within_its_own_geofence():
    assert is_within_airport_geofence(AIRPORT_LATITUDE, AIRPORT_LONGITUDE) is True


def test_central_london_is_outside_default_airport_geofence():
    assert is_within_airport_geofence(51.5074, -0.1278) is False


def test_distance_to_airport_km_matches_haversine():
    expected = haversine_km(51.5074, -0.1278, AIRPORT_LATITUDE, AIRPORT_LONGITUDE)
    assert distance_to_airport_km(51.5074, -0.1278) == expected
