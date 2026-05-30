"""
One place that builds the LLM client, so the rest of the app just calls get_llm().

It's cached, so we create the ChatNVIDIA client once and reuse it for every
request instead of rebuilding it each time.
"""
from functools import lru_cache

from langchain_nvidia_ai_endpoints import ChatNVIDIA

from app.config import settings

# Keep it low so answers stay grounded and consistent rather than creative.
_TEMPERATURE = 0.3
_MAX_TOKENS = 1024


@lru_cache(maxsize=1)
def get_llm():
    """The shared, streaming ChatNVIDIA client."""
    return ChatNVIDIA(
        model=settings.NVIDIA_MODEL,
        api_key=settings.NVIDIA_API_KEY,
        temperature=_TEMPERATURE,
        max_tokens=_MAX_TOKENS,
        streaming=True,
    )
