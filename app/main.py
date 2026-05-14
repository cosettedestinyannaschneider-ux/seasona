from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.api import api_router
from app.core.config import get_settings
from app.core.exception_handlers import install_exception_handlers


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
    )

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    install_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    media_mount_path = settings.media_url_prefix.rstrip("/") or "/media"
    settings.media_root.mkdir(parents=True, exist_ok=True)
    app.mount(media_mount_path, StaticFiles(directory=settings.media_root), name="media")

    @app.get("/")
    def root() -> dict[str, str]:
        return {"name": settings.app_name, "status": "ok"}

    return app


app = create_app()
