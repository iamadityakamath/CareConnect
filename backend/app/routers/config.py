from fastapi import APIRouter, Request
from fastapi.routing import APIRoute

from app.config import get_settings
from app.constants import CONTACT_PRESETS, MEDICAL_HISTORY_PRESETS, MEDICATION_PRESETS

router = APIRouter()

_SKIP_PATH_PREFIXES = ("/sample-webpage", "/test-ui", "/openapi.json", "/docs", "/redoc")


@router.get("/public")
def public_config():
    """Safe client-side config for test UI (no secrets)."""
    settings = get_settings()
    return {
        "supabase_url": settings.SUPABASE_URL,
        "supabase_anon_key": settings.SUPABASE_ANON_KEY,
    }


@router.get("/medication-presets")
def medication_presets():
    """Common medication templates for caregiver selection in the UI."""
    return {"presets": MEDICATION_PRESETS}


@router.get("/medical-history-presets")
def medical_history_presets():
    """Common medical history templates for caregiver selection in the UI."""
    return {"presets": MEDICAL_HISTORY_PRESETS}


@router.get("/contact-presets")
def contact_presets():
    """Common healthcare contact templates for caregiver selection in the UI."""
    return {"presets": CONTACT_PRESETS}


@router.get("/api-routes")
def api_routes(request: Request):
    """List all registered HTTP API routes grouped by router tag."""
    grouped: dict[str, list[dict]] = {}

    for route in request.app.routes:
        if not isinstance(route, APIRoute):
            continue
        if any(route.path.startswith(prefix) for prefix in _SKIP_PATH_PREFIXES):
            continue

        tag = (route.tags[0] if route.tags else "other").replace("-", " ").title()
        for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
            grouped.setdefault(tag, []).append(
                {
                    "method": method,
                    "path": route.path,
                    "name": route.name,
                    "summary": (route.summary or route.name or "").strip(),
                }
            )

    groups = []
    for tag in sorted(grouped.keys()):
        routes = sorted(grouped[tag], key=lambda r: (r["path"], r["method"]))
        prefix = routes[0]["path"].split("/")[1] if routes else tag.lower()
        groups.append({"tag": tag, "prefix": f"/{prefix}", "routes": routes})

    return {
        "title": request.app.title,
        "version": request.app.version,
        "groups": groups,
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "openapi_url": "/openapi.json",
    }
