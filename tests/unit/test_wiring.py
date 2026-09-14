from mardik.app import build_agent
from mardik.config import Settings
from mardik.telemetry import Telemetry


def test_build_agent_wires_telemetry(fake_llm):
    agent = build_agent(llm=fake_llm)
    try:
        assert isinstance(agent.telemetry, Telemetry)
    finally:
        agent.telemetry.shutdown()


def test_build_agent_wires_langfuse_when_configured(fake_llm):
    settings = Settings(
        azure_endpoint="",
        azure_api_key="",
        azure_model="Kimi-K2.6",
        otel_endpoint="http://localhost:4317",
        service_name="mardik",
        log_level="INFO",
        langfuse_host="http://localhost:3000",
        langfuse_public_key="pk-test",
        langfuse_secret_key="sk-test",
    )

    agent = build_agent(llm=fake_llm, settings=settings)
    try:
        assert isinstance(agent.telemetry, Telemetry)
    finally:
        agent.telemetry.shutdown()
