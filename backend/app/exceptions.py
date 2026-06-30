from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base application error."""

    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, status_code=404)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(message, status_code=401)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Forbidden"):
        super().__init__(message, status_code=403)


class ValidationError(AppError):
    def __init__(self, message: str = "Validation error"):
        super().__init__(message, status_code=422)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message},
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        """Return a safe client response for unexpected database/network failures."""
        message = str(exc).lower()
        if "readerror" in message or "connecterror" in message or "timeout" in message:
            return JSONResponse(
                status_code=503,
                content={"detail": "Database temporarily unavailable. Please try again."},
            )
        if "42703" in message or ("column" in message and "does not exist" in message):
            return JSONResponse(
                status_code=503,
                content={"detail": "Database schema mismatch. Contact support."},
            )
        return JSONResponse(
            status_code=500,
            content={"detail": "An unexpected error occurred."},
        )
