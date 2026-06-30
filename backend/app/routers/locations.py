from fastapi import APIRouter, Depends, Query

from app.dependencies import get_current_user
from app.services import places_service

router = APIRouter()


@router.get("/nearby-hospitals")
def nearby_hospitals(
    lat: float = Query(..., description="Latitude"),
    lng: float = Query(..., description="Longitude"),
    radius: int = Query(5000, description="Search radius in meters"),
    _current_user: dict = Depends(get_current_user),
):
    """Find nearby hospitals (requires authenticated caregiver or patient)."""
    return places_service.get_nearby_hospitals(lat, lng, radius)
