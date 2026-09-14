import threading

import pytest
from structlog.testing import capture_logs

from mardik.agent import Agent
from mardik.errors import LLMTimeoutError
from mardik.runner import load_session, replay
from mardik.session import SessionStore
from mardik.tools import DEFAULT_TOOLS


def _agent(llm, telemetry):
    return Agent(llm=llm, tools=DEFAULT_TOOLS, telemetry=telemetry)


def test_replay_preserves_session_context(fake_llm, telemetry):
    data = load_session("replay_delivery")
    result = replay(data, _agent(fake_llm, telemetry), SessionStore())
    assert "expédiée" in result.reply


def test_replay_smoke(fake_llm, telemetry):
    data = load_session("replay_delivery")
    result = replay(data, _agent(fake_llm, telemetry), SessionStore())
    assert result.reply is not None


def test_replay_timeout_incident(timeout_llm, telemetry):
    data = load_session("incident_timeout")
    with pytest.raises(LLMTimeoutError):
        replay(data, _agent(timeout_llm, telemetry), SessionStore())


def test_replay_timeout_increments_error_counter(timeout_llm, telemetry, metric_reader):
    data = load_session("incident_timeout")
    with pytest.raises(LLMTimeoutError):
        replay(data, _agent(timeout_llm, telemetry), SessionStore())

    metrics_data = metric_reader.get_metrics_data()
    points = [
        point
        for rm in metrics_data.resource_metrics
        for sm in rm.scope_metrics
        for metric in sm.metrics
        if metric.name == "errors_total"
        for point in metric.data.data_points
    ]
    assert points, "expected at least one errors_total measurement"


def test_replay_timeout_logs_failure(timeout_llm, telemetry):
    data = load_session("incident_timeout")
    with capture_logs() as logs:
        with pytest.raises(LLMTimeoutError):
            replay(data, _agent(timeout_llm, telemetry), SessionStore())

    events = [entry.get("event") for entry in logs]
    assert "turn.failed" in events


def test_replay_produces_single_connected_trace(fake_llm, telemetry, span_exporter):
    data = load_session("replay_delivery")
    replay(data, _agent(fake_llm, telemetry), SessionStore())

    spans = {span.name: span for span in span_exporter.get_finished_spans()}
    assert "agent.turn" in spans
    assert "llm.invoke" in spans
    assert "tool.call" in spans

    trace_ids = {span.context.trace_id for span in spans.values()}
    assert len(trace_ids) == 1


def test_replay_emits_latency_metric(fake_llm, telemetry, metric_reader):
    data = load_session("replay_delivery")
    replay(data, _agent(fake_llm, telemetry), SessionStore())

    metrics_data = metric_reader.get_metrics_data()
    points = [
        point
        for rm in metrics_data.resource_metrics
        for sm in rm.scope_metrics
        for metric in sm.metrics
        if metric.name == "latency_ms"
        for point in metric.data.data_points
    ]
    assert points, "expected at least one latency_ms measurement"


def test_replay_logs_turn_completion(fake_llm, telemetry):
    data = load_session("replay_delivery")
    with capture_logs() as logs:
        replay(data, _agent(fake_llm, telemetry), SessionStore())

    events = [entry.get("event") for entry in logs]
    assert "turn.completed" in events


def test_concurrent_replay_counts_every_turn(fake_llm, telemetry):
    data = load_session("incident_duplicate_delivery")
    agent = _agent(fake_llm, telemetry)
    store = SessionStore()

    def deliver() -> None:
        replay(data, agent, store)

    threads = [threading.Thread(target=deliver) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert store.turns(data["session_id"]) == 2
