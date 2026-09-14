"""Factory for the production LLM client (Azure AI Foundry, Kimi-K2.6)."""
from __future__ import annotations

from typing import Any

from .config import Settings


def get_llm(settings: Settings) -> Any:
    """Build the Azure-hosted chat model used in production.

    The endpoint (``.../openai/v1``) is an OpenAI-compatible route, not the
    native Azure AI Inference protocol — a plain OpenAI-compatible client is
    required. Imported lazily so the rest of the package does not require
    this SDK to be installed for offline test runs.
    """
    from langchain_openai import ChatOpenAI
    from pydantic import SecretStr

    return ChatOpenAI(
        base_url=settings.azure_endpoint,
        api_key=SecretStr(settings.azure_api_key),
        model=settings.azure_model,
    )
