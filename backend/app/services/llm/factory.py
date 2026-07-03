"""Build chat/embedding providers from settings."""

from app.core.config import Settings, get_settings
from app.services.llm.anthropic_provider import AnthropicProvider
from app.services.llm.base import ChatProvider, EmbeddingProvider
from app.services.llm.openai_compatible import (
    OllamaEmbeddings,
    OpenAICompatibleEmbeddings,
    OpenAICompatibleProvider,
)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def build_chat_provider(settings: Settings | None = None) -> ChatProvider:
    s = settings or get_settings()
    common = {"timeout": s.llm_timeout_seconds, "max_tokens": s.llm_max_output_tokens}
    if s.llm_provider == "anthropic":
        if not s.anthropic_api_key:
            raise RuntimeError("LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set")
        return AnthropicProvider(s.anthropic_api_key, s.anthropic_model, **common)
    if s.llm_provider == "openrouter":
        if not s.openrouter_api_key:
            raise RuntimeError("LLM_PROVIDER=openrouter but OPENROUTER_API_KEY is not set")
        return OpenAICompatibleProvider(
            OPENROUTER_BASE_URL,
            s.openrouter_model,
            api_key=s.openrouter_api_key,
            name="openrouter",
            extra_headers={
                "HTTP-Referer": "https://github.com/omrzk/opspilot-ai",
                "X-Title": "OpsPilot AI",
            },
            **common,
        )
    if s.llm_provider == "ollama":
        return OpenAICompatibleProvider(
            f"{s.ollama_base_url.rstrip('/')}/v1", s.ollama_model, name="ollama", **common
        )
    if s.llm_provider == "openai_compatible":
        if not s.openai_compatible_base_url or not s.openai_compatible_model:
            raise RuntimeError(
                "LLM_PROVIDER=openai_compatible requires OPENAI_COMPATIBLE_BASE_URL "
                "and OPENAI_COMPATIBLE_MODEL"
            )
        return OpenAICompatibleProvider(
            s.openai_compatible_base_url,
            s.openai_compatible_model,
            api_key=s.openai_compatible_api_key,
            **common,
        )
    raise RuntimeError(f"Unknown LLM_PROVIDER: {s.llm_provider}")


def build_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    s = settings or get_settings()
    if s.embedding_provider == "ollama":
        return OllamaEmbeddings(s.ollama_base_url, s.embedding_model)
    if s.embedding_provider == "openai_compatible":
        if not s.openai_compatible_base_url:
            raise RuntimeError(
                "EMBEDDING_PROVIDER=openai_compatible requires OPENAI_COMPATIBLE_BASE_URL"
            )
        return OpenAICompatibleEmbeddings(
            s.openai_compatible_base_url, s.embedding_model, api_key=s.openai_compatible_api_key
        )
    raise RuntimeError(f"Unknown EMBEDDING_PROVIDER: {s.embedding_provider}")
