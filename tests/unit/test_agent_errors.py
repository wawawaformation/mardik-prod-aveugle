import pytest
from structlog.testing import capture_logs

from mardik.agent import Agent
from mardik.errors import LLMTimeoutError
from mardik.session import SessionStore
from mardik.tools import DEFAULT_TOOLS


def test_llm_timeout_surfaces_as_domain_error(timeout_llm, telemetry):
    agent = Agent(llm=timeout_llm, tools=DEFAULT_TOOLS, telemetry=telemetry)
    with pytest.raises(LLMTimeoutError):
        agent.run_turn(SessionStore(), "err", "Bonjour")


def test_turn_failure_increments_error_counter(timeout_llm, telemetry, metric_reader):
    agent = Agent(llm=timeout_llm, tools=DEFAULT_TOOLS, telemetry=telemetry)
    with pytest.raises(LLMTimeoutError):
        agent.run_turn(SessionStore(), "err", "Bonjour")

    data = metric_reader.get_metrics_data()
    points = [
        point
        for rm in data.resource_metrics
        for sm in rm.scope_metrics
        for metric in sm.metrics
        if metric.name == "errors_total"
        for point in metric.data.data_points
    ]
    assert points, "expected at least one errors_total measurement"


def test_turn_failure_is_logged_structured(timeout_llm, telemetry):
    agent = Agent(llm=timeout_llm, tools=DEFAULT_TOOLS, telemetry=telemetry)
    with capture_logs() as logs:
        with pytest.raises(LLMTimeoutError):
            agent.run_turn(SessionStore(), "err", "Bonjour")

    events = [entry.get("event") for entry in logs]
    assert "turn.failed" in events
