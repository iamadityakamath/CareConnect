from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles
from starlette.responses import Response

from app.exceptions import register_exception_handlers
from app.routers import (
    auth,
    checkins,
    config,
    contacts,
    locations,
    medical_history,
    medications,
    patients,
    relationships,
    users,
)

app = FastAPI(title="CareConnect API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(config.router, prefix="/config", tags=["config"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(patients.router, prefix="/patients", tags=["patients"])
app.include_router(relationships.router, prefix="/relationships", tags=["relationships"])
app.include_router(medications.router, prefix="/medications", tags=["medications"])
app.include_router(checkins.router, prefix="/checkins", tags=["checkins"])
app.include_router(medical_history.router, prefix="/medical-history", tags=["medical-history"])
app.include_router(contacts.router, prefix="/contacts", tags=["contacts"])
app.include_router(locations.router, prefix="/locations", tags=["locations"])


@app.get("/health")
def health_check():
    return {"status": "ok"}


class NoCacheStaticFiles(StaticFiles):
    """Serve sample UI assets without aggressive browser caching during development."""

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if isinstance(response, Response) and response.status_code == 200:
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
        return response


_test_ui_dir = Path(__file__).resolve().parents[1] / "test-ui"
if _test_ui_dir.is_dir():
    app.mount("/test-ui", StaticFiles(directory=str(_test_ui_dir), html=True), name="test-ui")

_sample_web_dir = Path(__file__).resolve().parents[1] / "sample-webpage"
if _sample_web_dir.is_dir():
    app.mount(
        "/sample-webpage",
        NoCacheStaticFiles(directory=str(_sample_web_dir), html=True),
        name="sample-webpage",
    )
