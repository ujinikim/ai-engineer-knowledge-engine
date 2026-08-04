import logging
import re
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.settings import Settings, settings
from app.core.structured_logging import (
    get_logger,
    log_event,
    reset_request_id,
    set_request_id,
)


LOCAL_DEVELOPMENT_ORIGINS = {
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://0.0.0.0:5173",
}
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
logger = get_logger("api")


def allowed_cors_origins(app_settings: Settings) -> list[str]:
    origins = set(app_settings.cors_origins)
    if not app_settings.is_production:
        origins.update(LOCAL_DEVELOPMENT_ORIGINS)
    return sorted(origins)


def create_app(app_settings: Settings | None = None) -> FastAPI:
    active_settings = app_settings or settings
    application = FastAPI(title="AI Engineer Knowledge Engine")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_cors_origins(active_settings),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.middleware("http")
    async def structured_request_log(request: Request, call_next):
        supplied_request_id = request.headers.get("x-request-id", "")
        request_id = (
            supplied_request_id
            if REQUEST_ID_PATTERN.fullmatch(supplied_request_id)
            else uuid.uuid4().hex
        )
        request_token = set_request_id(request_id)
        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception as error:
            log_event(
                logger,
                "api_request_failed",
                level=logging.ERROR,
                method=request.method,
                path=request.url.path,
                status_code=status_code,
                duration_ms=int((time.perf_counter() - started) * 1000),
                exception_type=type(error).__name__,
            )
            raise
        finally:
            if request.url.path != "/health/live" or status_code >= 400:
                log_event(
                    logger,
                    "api_request_completed",
                    method=request.method,
                    path=request.url.path,
                    status_code=status_code,
                    duration_ms=int((time.perf_counter() - started) * 1000),
                )
            reset_request_id(request_token)

    # Keep root routes for local/backward-compatible clients while exposing the
    # same API behind CloudFront's unambiguous /api/* production behavior.
    application.include_router(router)
    application.include_router(router, prefix="/api")
    return application


app = create_app()
