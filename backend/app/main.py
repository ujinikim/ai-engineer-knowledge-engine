from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.settings import Settings, settings


LOCAL_DEVELOPMENT_ORIGINS = {
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://0.0.0.0:5173",
}


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
    application.include_router(router)
    return application


app = create_app()
