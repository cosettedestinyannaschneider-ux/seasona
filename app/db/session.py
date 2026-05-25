from collections.abc import Generator
from typing import Any

from app.core.config import get_settings


_engine = None
_session_factory = None


def get_engine():
    global _engine
    if _engine is None:
        from sqlalchemy import create_engine

        settings = get_settings()
        if not settings.database_url:
            raise RuntimeError("SEASONA_DATABASE_URL is not configured.")
        engine_kwargs: dict[str, Any] = {"pool_pre_ping": True}
        if not settings.database_url.startswith("sqlite"):
            engine_kwargs.update(
                {
                    "pool_size": settings.database_pool_size,
                    "max_overflow": settings.database_max_overflow,
                    "pool_timeout": settings.database_pool_timeout_seconds,
                    "pool_recycle": settings.database_pool_recycle_seconds,
                }
            )
        _engine = create_engine(settings.database_url, **engine_kwargs)
    return _engine


def get_session_factory():
    global _session_factory
    if _session_factory is None:
        from sqlalchemy.orm import sessionmaker

        _session_factory = sessionmaker(
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
            bind=get_engine(),
        )
    return _session_factory


def get_db() -> Generator[Any, None, None]:
    from sqlalchemy.orm import Session

    db: Session = get_session_factory()()
    try:
        yield db
    finally:
        db.close()
