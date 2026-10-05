"""Geographic Velocity & Impossible Travel Anomaly Detection Engine for Omerta.ai.

Calculates geodesic distance (Haversine formula), elapsed travel time, and velocity (km/h)
between consecutive customer sessions, logins, and transfer origins.
Detects impossible travel velocities (e.g. Cairo to Port Said in 5 minutes, or Cairo to London in 10 minutes)
and escalates account risk.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
import math
from typing import Any

# Geocoordinates dictionary for Egyptian governorates & major global cities
LOCATION_COORDINATES: dict[str, tuple[float, float]] = {
    # Egypt Major Cities & Governorates
    "cairo": (30.0444, 31.2357),
    "giza": (30.0131, 31.2089),
    "alexandria": (31.2001, 29.9187),
    "port said": (31.2653, 32.3019),
    "bur said": (31.2653, 32.3019),
    "bursaid": (31.2653, 32.3019),
    "suez": (29.9668, 32.5498),
    "ismailia": (30.5965, 32.2715),
    "mansoura": (31.0409, 31.3785),
    "tanta": (30.7865, 31.0004),
    "aswan": (24.0889, 32.8998),
    "luxor": (25.6872, 32.6396),
    "hurghada": (27.2579, 33.8116),
    "sharm el sheikh": (27.9158, 34.3299),
    "fayoum": (29.3084, 30.8428),
    "zagazig": (30.5877, 31.5020),
    "damietta": (31.4175, 31.8144),
    
    # Global Major Hubs
    "london": (51.5074, -0.1278),
    "paris": (48.8566, 2.3522),
    "berlin": (52.5200, 13.4050),
    "amsterdam": (52.3676, 4.9041),
    "frankfurt": (50.1109, 8.6821),
    "dubai": (25.2048, 55.2708),
    "riyadh": (24.7136, 46.6753),
    "jeddah": (21.4858, 39.1925),
    "kuwait city": (29.3759, 47.9774),
    "doha": (25.2854, 51.5310),
    "abu dhabi": (24.4539, 54.3773),
    "new york": (40.7128, -74.0060),
    "san francisco": (37.7749, -122.4194),
    "los angeles": (34.0522, -118.2437),
    "tokyo": (35.6762, 139.6503),
    "singapore": (1.3521, 103.8198),
}

# Country centroid approximations
COUNTRY_CENTROIDS: dict[str, tuple[float, float]] = {
    "EG": (26.8206, 30.8025),
    "SA": (23.8859, 45.0792),
    "AE": (23.4241, 53.8478),
    "KW": (29.3117, 47.4818),
    "QA": (25.3548, 51.1839),
    "US": (37.0902, -95.7129),
    "GB": (55.3781, -3.4360),
    "DE": (51.1657, 10.4515),
    "FR": (46.2276, 2.2137),
    "NL": (52.1326, 5.2913),
    "JP": (36.2048, 138.2529),
    "SG": (1.3521, 103.8198),
}


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points on the Earth (Haversine)."""
    R = 6371.0  # Earth's radius in kilometers

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(R * c, 2)


def resolve_coordinates(city: str | None = None, country: str | None = None) -> tuple[float, float]:
    """Resolve latitude and longitude from city name or country code."""
    if city:
        clean_city = city.strip().lower()
        if clean_city in LOCATION_COORDINATES:
            return LOCATION_COORDINATES[clean_city]
        for known_city, coords in LOCATION_COORDINATES.items():
            if known_city in clean_city or clean_city in known_city:
                return coords

    clean_country = (country or "EG").strip().upper()
    if clean_country in COUNTRY_CENTROIDS:
        return COUNTRY_CENTROIDS[clean_country]

    return (30.0444, 31.2357)  # Default Cairo, Egypt


@dataclass
class VelocityAnalysisResult:
    is_impossible_travel: bool
    distance_km: float
    elapsed_minutes: float
    calculated_speed_kmh: float
    origin: str
    destination: str
    risk_score_penalty: float
    reason: str | None = None


def evaluate_geographic_velocity(
    *,
    prev_country: str | None,
    prev_city: str | None,
    prev_timestamp: datetime | None,
    current_country: str | None,
    current_city: str | None,
    current_timestamp: datetime | None = None,
) -> VelocityAnalysisResult:
    """Analyze travel velocity between previous and current activity.
    
    Triggers an anomaly if:
    1. Distance > 50km within 15 minutes (speed > 200 km/h ground speed without aviation).
    2. Different countries traversed within 1 hour (inter-continental impossible velocity).
    3. Calculated velocity exceeds 850 km/h (maximum commercial flight speed including boarding).
    """
    now = current_timestamp or datetime.now(UTC)
    if not prev_timestamp:
        return VelocityAnalysisResult(
            is_impossible_travel=False,
            distance_km=0.0,
            elapsed_minutes=0.0,
            calculated_speed_kmh=0.0,
            origin=f"{prev_city or 'Unknown'}, {prev_country or 'EG'}",
            destination=f"{current_city or 'Unknown'}, {current_country or 'EG'}",
            risk_score_penalty=0.0,
            reason=None,
        )

    # Calculate elapsed time
    if prev_timestamp.tzinfo is None:
        prev_timestamp = prev_timestamp.replace(tzinfo=UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    elapsed_seconds = max((now - prev_timestamp).total_seconds(), 1.0)
    elapsed_minutes = round(elapsed_seconds / 60.0, 2)
    elapsed_hours = elapsed_seconds / 3600.0

    # Resolve coordinates
    lat1, lon1 = resolve_coordinates(prev_city, prev_country)
    lat2, lon2 = resolve_coordinates(current_city, current_country)

    distance_km = haversine_distance_km(lat1, lon1, lat2, lon2)
    speed_kmh = round(distance_km / max(elapsed_hours, 0.001), 1)

    origin_label = f"{prev_city.title() if prev_city else (prev_country or 'EG')}"
    dest_label = f"{current_city.title() if current_city else (current_country or 'EG')}"

    # Velocity Anomaly Conditions
    is_anomaly = False
    penalty = 0.0
    reason = None

    # Condition A: Short time window (under 15 mins) with significant distance (> 50 km)
    # (e.g. Cairo to Port Said ~205 km in 5 mins)
    if elapsed_minutes <= 15.0 and distance_km > 50.0:
        is_anomaly = True
        penalty = 65.0
        reason = (
            f"Impossible Travel Velocity: Traversed {distance_km} km in {elapsed_minutes} minutes "
            f"(Calculated Speed: {speed_kmh:,.1f} km/h) from {origin_label} to {dest_label}."
        )

    # Condition B: Inter-country travel under 60 minutes
    elif elapsed_minutes <= 60.0 and (prev_country or "").upper() != (current_country or "").upper() and distance_km > 300.0:
        is_anomaly = True
        penalty = 75.0
        reason = (
            f"Geographic Impossibility: Cross-border access between {origin_label} and {dest_label} "
            f"observed within {elapsed_minutes} minutes ({distance_km} km, {speed_kmh:,.1f} km/h)."
        )

    # Condition C: Velocity exceeds supersonic flight limits (> 900 km/h)
    elif speed_kmh > 900.0 and distance_km > 100.0:
        is_anomaly = True
        penalty = 80.0
        reason = (
            f"Supersonic Velocity Anomaly: {distance_km} km distance traversed at {speed_kmh:,.1f} km/h "
            f"between {origin_label} and {dest_label}."
        )

    return VelocityAnalysisResult(
        is_impossible_travel=is_anomaly,
        distance_km=distance_km,
        elapsed_minutes=elapsed_minutes,
        calculated_speed_kmh=speed_kmh,
        origin=origin_label,
        destination=dest_label,
        risk_score_penalty=penalty,
        reason=reason,
    )
