from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str
    SUPABASE_ANON_KEY: str
    SUPABASE_JWT_SECRET: str
    DATABASE_URL: str = ""
    GOOGLE_PLACES_API_KEY: str = ""
    ENVIRONMENT: str = "development"
    PATIENT_AUTH_EMAIL_DOMAIN: str = "careconnect.internal"
    PATIENT_SESSION_DAYS: int = 30

    model_config = SettingsConfigDict(env_file=".env")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
