from functools import lru_cache

from supabase import Client, create_client

from app.config import get_settings


@lru_cache()
def get_supabase_client() -> Client:
    """
    Returns a cached singleton Supabase client.
    lru_cache ensures this only runs once per process,
    regardless of how many times it's called or imported.
    """
    settings = get_settings()
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
