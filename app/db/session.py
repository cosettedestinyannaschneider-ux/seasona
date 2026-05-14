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
        _engine = create_engine(settings.database_url, pool_pre_ping=True)
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
