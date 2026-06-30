"""CORS configuration for browser clients (local dev, Vercel, separate frontends)."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings


def configure_cors(app: FastAPI) -> None:
    """Allow browser clients from configured origins (default: all origins)."""
    settings = get_settings()
    origins = settings.CORS_ALLOW_ORIGINS.strip()

    common_kwargs = {
        "allow_methods": ["*"],
        "allow_headers": ["*"],
        "expose_headers": ["*"],
        "max_age": 86400,
    }

    if origins == "*":
        # Echo any Origin header back — works for cross-origin API calls with Authorization.
        app.add_middleware(
            CORSMiddleware,
            allow_origin_regex=r".*",
            allow_credentials=True,
            **common_kwargs,
        )
        return

    origin_list = [origin.strip() for origin in origins.split(",") if origin.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origin_list or ["*"],
        allow_credentials=True,
        **common_kwargs,
    )
