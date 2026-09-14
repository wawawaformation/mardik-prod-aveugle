"""Runtime configuration loaded from the environment."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    azure_endpoint: str
    azure_api_key: str
    azure_model: str
    otel_endpoint: str
    service_name: str
    log_level: str
    langfuse_host: str
    langfuse_public_key: str
    langfuse_secret_key: str


def load_settings() -> Settings:
    return Settings(
        azure_endpoint=os.environ.get("AZURE_AI_ENDPOINT", ""),
        azure_api_key=os.environ.get("AZURE_AI_API_KEY", ""),
        azure_model=os.environ.get("AZURE_AI_MODEL", "Kimi-K2.6"),
        otel_endpoint=os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"),
        service_name=os.environ.get("OTEL_SERVICE_NAME", "mardik"),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
        langfuse_host=os.environ.get("LANGFUSE_HOST", "http://localhost:3000"),
        langfuse_public_key=os.environ.get("LANGFUSE_PUBLIC_KEY", ""),
        langfuse_secret_key=os.environ.get("LANGFUSE_SECRET_KEY", ""),
    )
