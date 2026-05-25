from functools import lru_cache
import os
from pathlib import Path

from pydantic import BaseModel


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_ENV_FILE = ROOT_DIR / ".env"


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _env_int(name: str, default: int) -> int:
    value = _env(name)
    return int(value) if value else default


def _env_float(name: str, default: float) -> float:
    value = _env(name)
    return float(value) if value else default


def _env_bool(name: str, default: bool) -> bool:
    value = _env(name)
    if not value:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _env_csv(name: str) -> list[str]:
    value = _env(name)
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings(BaseModel):
    app_name: str = "Seasona"
    app_version: str = "0.1.0"
    environment: str = "local"
    api_v1_prefix: str = "/api/v1"

    database_url: str = ""
    database_pool_size: int = 5
    database_max_overflow: int = 5
    database_pool_timeout_seconds: int = 30
    database_pool_recycle_seconds: int = 1800
    redis_url: str = ""
    redis_socket_timeout_seconds: float = 1.0
    redis_socket_connect_timeout_seconds: float = 1.0
    redis_health_check_interval_seconds: int = 30
    meilisearch_url: str = ""
    meilisearch_api_key: str = ""
    meilisearch_index: str = "seasona_products"
    meilisearch_embedder: str = "products"
    meilisearch_home_semantic_ratio: float = 0.5
    meilisearch_ai_semantic_ratio: float = 0.3
    meilisearch_ai_ranking_score_threshold: float = 0.3

    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "seasona"
    jwt_audience: str = "seasona-users"
    access_token_expire_minutes: int = 60
    password_reset_token_expire_minutes: int = 15
    auth_rate_limit_enabled: bool = True
    auth_rate_limit_window_seconds: int = 10
    auth_login_ip_limit: int = 300
    auth_login_identifier_limit: int = 100
    auth_register_ip_limit: int = 100
    auth_password_reset_ip_limit: int = 100
    auth_password_reset_identifier_limit: int = 50
    argon2_time_cost: int = 2
    argon2_memory_cost: int = 19456
    argon2_parallelism: int = 1
    argon2_hash_len: int = 32
    argon2_salt_len: int = 16

    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = ""
    embedding_api_key: str = ""
    embedding_base_url: str = ""
    embedding_model: str = ""

    media_root: Path = ROOT_DIR / "media"
    media_url_prefix: str = "/media"
    max_upload_size_mb: int = 8

    cors_origins: list[str] = []


@lru_cache
def get_settings() -> Settings:
    _load_env_file(DEFAULT_ENV_FILE)
    return Settings(
        app_name=_env("SEASONA_APP_NAME", "Seasona"),
        app_version=_env("SEASONA_APP_VERSION", "0.1.0"),
        environment=_env("SEASONA_ENVIRONMENT", "local"),
        api_v1_prefix=_env("SEASONA_API_V1_PREFIX", "/api/v1"),
        database_url=_env("SEASONA_DATABASE_URL"),
        database_pool_size=_env_int("SEASONA_DB_POOL_SIZE", 5),
        database_max_overflow=_env_int("SEASONA_DB_MAX_OVERFLOW", 5),
        database_pool_timeout_seconds=_env_int("SEASONA_DB_POOL_TIMEOUT_SECONDS", 30),
        database_pool_recycle_seconds=_env_int("SEASONA_DB_POOL_RECYCLE_SECONDS", 1800),
        redis_url=_env("SEASONA_REDIS_URL"),
        redis_socket_timeout_seconds=_env_float("SEASONA_REDIS_SOCKET_TIMEOUT_SECONDS", 1.0),
        redis_socket_connect_timeout_seconds=_env_float(
            "SEASONA_REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS",
            1.0,
        ),
        redis_health_check_interval_seconds=_env_int("SEASONA_REDIS_HEALTH_CHECK_INTERVAL_SECONDS", 30),
        meilisearch_url=_env("SEASONA_MEILISEARCH_URL"),
        meilisearch_api_key=_env("SEASONA_MEILISEARCH_API_KEY"),
        meilisearch_index=_env("SEASONA_MEILISEARCH_INDEX", "seasona_products"),
        meilisearch_embedder=_env("SEASONA_MEILISEARCH_EMBEDDER", "products"),
        meilisearch_home_semantic_ratio=_env_float(
            "SEASONA_MEILISEARCH_HOME_SEMANTIC_RATIO", 0.5
        ),
        meilisearch_ai_semantic_ratio=_env_float(
            "SEASONA_MEILISEARCH_AI_SEMANTIC_RATIO", 0.3
        ),
        meilisearch_ai_ranking_score_threshold=_env_float(
            "SEASONA_MEILISEARCH_AI_RANKING_SCORE_THRESHOLD", 0.3
        ),
        jwt_secret_key=_env("SEASONA_JWT_SECRET_KEY"),
        jwt_algorithm=_env("SEASONA_JWT_ALGORITHM", "HS256"),
        jwt_issuer=_env("SEASONA_JWT_ISSUER", "seasona"),
        jwt_audience=_env("SEASONA_JWT_AUDIENCE", "seasona-users"),
        access_token_expire_minutes=_env_int(
            "SEASONA_ACCESS_TOKEN_EXPIRE_MINUTES", 60
        ),
        password_reset_token_expire_minutes=_env_int(
            "SEASONA_PASSWORD_RESET_TOKEN_EXPIRE_MINUTES", 15
        ),
        auth_rate_limit_enabled=_env_bool("SEASONA_AUTH_RATE_LIMIT_ENABLED", True),
        auth_rate_limit_window_seconds=_env_int("SEASONA_AUTH_RATE_LIMIT_WINDOW_SECONDS", 10),
        auth_login_ip_limit=_env_int("SEASONA_AUTH_LOGIN_IP_LIMIT", 300),
        auth_login_identifier_limit=_env_int("SEASONA_AUTH_LOGIN_IDENTIFIER_LIMIT", 100),
        auth_register_ip_limit=_env_int("SEASONA_AUTH_REGISTER_IP_LIMIT", 100),
        auth_password_reset_ip_limit=_env_int("SEASONA_AUTH_PASSWORD_RESET_IP_LIMIT", 100),
        auth_password_reset_identifier_limit=_env_int(
            "SEASONA_AUTH_PASSWORD_RESET_IDENTIFIER_LIMIT",
            50,
        ),
        argon2_time_cost=_env_int("SEASONA_ARGON2_TIME_COST", 2),
        argon2_memory_cost=_env_int("SEASONA_ARGON2_MEMORY_COST", 19456),
        argon2_parallelism=_env_int("SEASONA_ARGON2_PARALLELISM", 1),
        argon2_hash_len=_env_int("SEASONA_ARGON2_HASH_LEN", 32),
        argon2_salt_len=_env_int("SEASONA_ARGON2_SALT_LEN", 16),
        llm_api_key=_env("SEASONA_LLM_API_KEY"),
        llm_base_url=_env("SEASONA_LLM_BASE_URL"),
        llm_model=_env("SEASONA_LLM_MODEL"),
        embedding_api_key=_env("SEASONA_EMBEDDING_API_KEY"),
        embedding_base_url=_env("SEASONA_EMBEDDING_BASE_URL"),
        embedding_model=_env("SEASONA_EMBEDDING_MODEL"),
        media_root=Path(_env("SEASONA_MEDIA_ROOT", str(ROOT_DIR / "media"))),
        media_url_prefix=_env("SEASONA_MEDIA_URL_PREFIX", "/media"),
        max_upload_size_mb=_env_int("SEASONA_MAX_UPLOAD_SIZE_MB", 8),
        cors_origins=_env_csv("SEASONA_CORS_ORIGINS"),
    )
