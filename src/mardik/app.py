"""Application wiring: build a ready-to-run agent and a CLI entrypoint."""
from __future__ import annotations

from typing import Any

from .agent import Agent
from .config import Settings, load_settings
from .session import SessionStore
from .tools import DEFAULT_TOOLS


def build_agent(
    llm: Any | None = None,
    telemetry: Any | None = None,
    settings: Settings | None = None,
) -> Agent:
    """Assemble the production agent from configuration."""
    settings = settings or load_settings()
    if llm is None:
        from .llm import get_llm

        llm = get_llm(settings)
    if telemetry is None:
        from .telemetry import build_default_telemetry

        telemetry = build_default_telemetry(
            level=settings.log_level,
            service_name=settings.service_name,
            langfuse_host=settings.langfuse_host,
            langfuse_public_key=settings.langfuse_public_key,
            langfuse_secret_key=settings.langfuse_secret_key,
        )
    return Agent(llm=llm, tools=DEFAULT_TOOLS, telemetry=telemetry)


def main() -> None:
    settings = load_settings()
    agent = build_agent(settings=settings)
    store = SessionStore()
    result = agent.run_turn(store, "cli", "Bonjour")
    print(result.reply)


if __name__ == "__main__":
    main()
