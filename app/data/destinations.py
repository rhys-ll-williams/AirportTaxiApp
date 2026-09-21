"""Static destination lookup used to auto-classify fares.

This stands in for a real distance/drive-time API. Each entry gives the
typical *round trip* time (rank to destination and back to the airport),
which is what the exemption time limit is based on. Rank agents can always
override the classification and round-trip estimate for a destination that
isn't listed, or where local knowledge (traffic, roadworks) suggests a
different estimate.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from app.models import FareClassification


@dataclass(frozen=True)
class DestinationInfo:
    classification: FareClassification
    typical_round_trip_minutes: float


# Local: nearby destinations within London, typically <= 1h round trip.
# Fares Fare: destinations outside London, within a reasonable distance
# (roughly a 1h15 round trip).
KNOWN_DESTINATIONS: Dict[str, DestinationInfo] = {
    "central london": DestinationInfo(FareClassification.LOCAL, 55),
    "paddington": DestinationInfo(FareClassification.LOCAL, 50),
    "kensington": DestinationInfo(FareClassification.LOCAL, 45),
    "chelsea": DestinationInfo(FareClassification.LOCAL, 45),
    "hammersmith": DestinationInfo(FareClassification.LOCAL, 35),
    "ealing": DestinationInfo(FareClassification.LOCAL, 30),
    "richmond": DestinationInfo(FareClassification.LOCAL, 35),
    "hounslow": DestinationInfo(FareClassification.LOCAL, 25),
    "uxbridge": DestinationInfo(FareClassification.LOCAL, 30),
    "canary wharf": DestinationInfo(FareClassification.LOCAL, 60),
    "victoria": DestinationInfo(FareClassification.LOCAL, 50),
    "heathrow hotel": DestinationInfo(FareClassification.LOCAL, 20),
    "windsor": DestinationInfo(FareClassification.FARES_FARE, 65),
    "reading": DestinationInfo(FareClassification.FARES_FARE, 75),
    "maidenhead": DestinationInfo(FareClassification.FARES_FARE, 60),
    "woking": DestinationInfo(FareClassification.FARES_FARE, 70),
    "guildford": DestinationInfo(FareClassification.FARES_FARE, 80),
    "basingstoke": DestinationInfo(FareClassification.FARES_FARE, 90),
    "st albans": DestinationInfo(FareClassification.FARES_FARE, 85),
    "watford": DestinationInfo(FareClassification.FARES_FARE, 70),
}


def find_destination(normalized_text: str) -> Optional[DestinationInfo]:
    """Best-effort match of free-text destination input against known places."""
    if not normalized_text:
        return None
    if normalized_text in KNOWN_DESTINATIONS:
        return KNOWN_DESTINATIONS[normalized_text]
    for key, info in KNOWN_DESTINATIONS.items():
        if key in normalized_text or normalized_text in key:
            return info
    return None
