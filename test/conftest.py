from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker


os.environ.setdefault("SEASONA_ENVIRONMENT", "test")
os.environ.setdefault("SEASONA_JWT_SECRET_KEY", "test-secret-key")
os.environ.setdefault("SEASONA_ARGON2_TIME_COST", "1")
os.environ.setdefault("SEASONA_ARGON2_MEMORY_COST", "8192")
os.environ.setdefault("SEASONA_ARGON2_PARALLELISM", "1")
os.environ.setdefault("SEASONA_MEDIA_ROOT", str(Path.cwd() / "test" / "media"))
os.environ.setdefault("SEASONA_REDIS_URL", "")

from app.core.cache import InMemoryTokenBlocklistStore, get_token_blocklist_store
from app.core.config import Settings, get_settings
from app.core.redis import get_redis_client


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "integration: requires PostgreSQL test database")


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    get_settings.cache_clear()
    settings = get_settings()
    return settings.model_copy(
        update={
            "environment": "test",
            "jwt_secret_key": "test-secret-key",
            "redis_url": "",
            "meilisearch_url": "",
            "meilisearch_api_key": "",
            "llm_model": "",
            "media_root": Path.cwd() / "test" / "media",
            "argon2_time_cost": 1,
            "argon2_memory_cost": 8192,
            "argon2_parallelism": 1,
        }
    )


@pytest.fixture(scope="session")
def test_database_url() -> str | None:
    return os.getenv("SEASONA_TEST_DATABASE_URL")


@pytest.fixture(scope="session")
def db_engine(test_database_url: str | None):
    if not test_database_url:
        pytest.skip("SEASONA_TEST_DATABASE_URL is not configured.")
    import app.models  # noqa: F401
    from app.db.base import Base

    engine = create_engine(test_database_url, pool_pre_ping=True)
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def db_session(db_engine) -> Generator[Session, None, None]:
    connection = db_engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        bind=connection,
    )
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def app_client(db_session: Session, test_settings: Settings):
    from fastapi.testclient import TestClient

    from app.core.dependencies import get_db
    from app.main import app

    def override_settings() -> Settings:
        return test_settings

    def override_db() -> Generator[Session, None, None]:
        yield db_session

    token_store = InMemoryTokenBlocklistStore()

    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_token_blocklist_store] = lambda: token_store
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def isolate_settings_cache():
    get_settings.cache_clear()
    get_token_blocklist_store.cache_clear()
    get_redis_client.cache_clear()
    yield
    get_settings.cache_clear()
    get_token_blocklist_store.cache_clear()
    get_redis_client.cache_clear()
