from openai import OpenAI
import httpx

from app.core.config import get_settings


def get_llm_client() -> OpenAI:
    settings = get_settings()
    if not settings.llm_api_key or not settings.llm_base_url:
        raise RuntimeError("LLM configuration is incomplete.")
    return OpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        timeout=settings.llm_timeout_seconds,
        http_client=httpx.Client(
            trust_env=False,
            timeout=httpx.Timeout(settings.llm_timeout_seconds),
        ),
    )
