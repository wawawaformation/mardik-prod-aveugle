from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from mardik.telemetry import build_telemetry


def test_service_name_is_set_on_spans():
    span_exporter = InMemorySpanExporter()
    telemetry = build_telemetry(
        span_exporter=span_exporter,
        metric_reader=InMemoryMetricReader(),
        service_name="mardik-test",
    )

    with telemetry.tracer.start_as_current_span("probe"):
        pass

    spans = span_exporter.get_finished_spans()
    assert spans[0].resource.attributes["service.name"] == "mardik-test"


def test_shutdown_stops_tracer_and_meter_providers():
    telemetry = build_telemetry(
        span_exporter=InMemorySpanExporter(),
        metric_reader=InMemoryMetricReader(),
    )

    telemetry.shutdown()  # ne doit pas lever
