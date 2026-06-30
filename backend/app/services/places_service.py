import math

import httpx

from app.config import get_settings
from app.exceptions import ValidationError


def _haversine_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate distance in meters between two coordinates."""
    r = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def get_nearby_hospitals(lat: float, lng: float, radius: int = 5000) -> list[dict]:
    """Fetch nearby hospitals from Google Places API."""
    if not (-90 <= lat <= 90):
        raise ValidationError("Invalid latitude")
    if not (-180 <= lng <= 180):
        raise ValidationError("Invalid longitude")
    if radius < 100 or radius > 50000:
        raise ValidationError("Radius must be between 100 and 50000 meters")

    settings = get_settings()
    if not settings.GOOGLE_PLACES_API_KEY:
        raise ValidationError("Google Places API key not configured")

    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        "location": f"{lat},{lng}",
        "radius": radius,
        "type": "hospital",
        "key": settings.GOOGLE_PLACES_API_KEY,
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError:
        raise ValidationError("Failed to fetch nearby hospitals")

    if data.get("status") not in ("OK", "ZERO_RESULTS"):
        raise ValidationError("Places API returned an error")

    results = []
    for place in data.get("results", []):
        place_lat = place.get("geometry", {}).get("location", {}).get("lat")
        place_lng = place.get("geometry", {}).get("location", {}).get("lng")
        distance = None
        if place_lat is not None and place_lng is not None:
            distance = round(_haversine_meters(lat, lng, place_lat, place_lng))

        results.append({
            "name": place.get("name"),
            "address": place.get("vicinity"),
            "phone": None,
            "distance_meters": distance,
            "open_now": place.get("opening_hours", {}).get("open_now"),
            "place_id": place.get("place_id"),
        })

    results.sort(key=lambda x: x["distance_meters"] or float("inf"))
    return results
