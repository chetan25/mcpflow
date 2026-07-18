"""Provider-agnostic LLM integration for ChatManager.

ChatManager depends only on the LLMProvider protocol - never a specific
SDK - so any backend can be plugged in by implementing it. Two adapters
ship in mcpflow itself: OpenAICompatibleProvider (zero extra dependency,
covers anything speaking the OpenAI chat-completions wire format) and
LiteLLMProvider (optional, broader native provider coverage).
"""

from .base import LLMMessage, LLMProvider, LLMResponse, LLMToolCall
from .openai_compatible import OpenAICompatibleProvider
from .litellm_provider import LiteLLMProvider


def build_provider_from_config(model_config) -> LLMProvider:
    """
    Build an LLMProvider from a ModelConfig.

    Args:
        model_config: An mcpflow.config.ModelConfig-shaped object (duck
            typed on .provider/.base_url/.api_key so this has no import
            dependency on mcpflow.config)

    Returns:
        LiteLLMProvider if model_config.provider == "litellm", otherwise
        OpenAICompatibleProvider configured from base_url/api_key.

    Raises:
        ValueError: If provider isn't "litellm" and no base_url is set
    """
    if model_config.provider == "litellm":
        return LiteLLMProvider()

    if not model_config.base_url:
        raise ValueError(
            f"ModelConfig for provider '{model_config.provider}' has no base_url; "
            "OpenAICompatibleProvider requires one (e.g. an OpenRouter or Ollama endpoint)"
        )

    return OpenAICompatibleProvider(
        base_url=model_config.base_url, api_key=model_config.api_key
    )


__all__ = [
    "LLMMessage",
    "LLMProvider",
    "LLMResponse",
    "LLMToolCall",
    "OpenAICompatibleProvider",
    "LiteLLMProvider",
    "build_provider_from_config",
]
