import base64

from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from mardik.telemetry import build_default_telemetry, build_telemetry


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


def test_extra_span_exporters_receive_the_same_spans():
    primary_exporter = InMemorySpanExporter()
    secondary_exporter = InMemorySpanExporter()
    telemetry = build_telemetry(
        span_exporter=primary_exporter,
        metric_reader=InMemoryMetricReader(),
        extra_span_exporters=[secondary_exporter],
    )

    with telemetry.tracer.start_as_current_span("probe"):
        pass
    telemetry.shutdown()

    assert len(primary_exporter.get_finished_spans()) == 1
    assert len(secondary_exporter.get_finished_spans()) == 1


def test_langfuse_auth_header_is_basic_base64():
    from mardik.telemetry import _langfuse_auth_header

    header = _langfuse_auth_header("pk-test", "sk-test")

    assert header == "Basic " + base64.b64encode(b"pk-test:sk-test").decode()


def test_build_default_telemetry_without_langfuse_keys_does_not_raise():
    telemetry = build_default_telemetry(langfuse_public_key="", langfuse_secret_key="")
    telemetry.shutdown()


def test_build_default_telemetry_with_langfuse_keys_does_not_raise():
    telemetry = build_default_telemetry(
        langfuse_host="http://localhost:3000",
        langfuse_public_key="pk-test",
        langfuse_secret_key="sk-test",
    )
    telemetry.shutdown()
