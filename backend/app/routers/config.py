from fastapi import APIRouter

from app.config import get_settings

router = APIRouter()


@router.get("/public")
def public_config():
    """Safe client-side config for test UI (no secrets)."""
    settings = get_settings()
    return {
        "supabase_url": settings.SUPABASE_URL,
        "supabase_anon_key": settings.SUPABASE_ANON_KEY,
    }
