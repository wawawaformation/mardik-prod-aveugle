"""Observability primitives: structured logging, tracing and metrics.

The :class:`Telemetry` object bundles a tracer, a logger and the metric
instruments the agent emits. It is injectable so that tests can wire in-memory
exporters and inspect what was recorded; production wiring lives in
:func:`build_default_telemetry`.
"""
from __future__ import annotations

import base64
import logging

import structlog
from opentelemetry.metrics import Meter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    MetricReader,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    ConsoleSpanExporter,
    SimpleSpanProcessor,
    SpanExporter,
)
from opentelemetry.trace import Tracer


def configure_logging(level: str = "INFO") -> None:
    """Configure structlog to emit structured JSON lines."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(level.upper())
        ),
        cache_logger_on_first_use=False,
    )


class Telemetry:
    """Bundle of tracer + logger + metric instruments used by the agent."""

    def __init__(
        self,
        tracer: Tracer,
        meter: Meter,
        tracer_provider: TracerProvider | None = None,
        meter_provider: MeterProvider | None = None,
    ) -> None:
        self.tracer = tracer
        self.logger = structlog.get_logger("mardik")
        self.latency_ms = meter.create_histogram(
            "latency_ms",
            unit="ms",
            description="End-to-end latency of an agent turn.",
        )
        self.errors = meter.create_counter(
            "errors_total",
            description="Count of agent turns that ended in an error.",
        )
        self._tracer_provider = tracer_provider
        self._meter_provider = meter_provider

    def record_latency(self, value_ms: float, **attributes: str) -> None:
        self.latency_ms.record(value_ms, attributes=attributes)

    def shutdown(self) -> None:
        """Stop background export threads (e.g. periodic metric export).

        Sans cet appel, le MeterProvider continue d'exporter en tâche de
        fond après la fin du programme (ou d'un test) et peut tenter
        d'écrire sur un flux déjà fermé.
        """
        if self._tracer_provider is not None:
            self._tracer_provider.shutdown()
        if self._meter_provider is not None:
            self._meter_provider.shutdown()


def build_telemetry(
    span_exporter: SpanExporter | None = None,
    metric_reader: MetricReader | None = None,
    level: str = "INFO",
    service_name: str = "mardik",
    environment: str = "development",
    extra_span_exporters: list[SpanExporter] | None = None,
) -> Telemetry:
    """Build a self-contained Telemetry bundle.

    Defaults to console exporters; tests pass in-memory exporters/readers.
    ``extra_span_exporters`` reçoit chacun son propre SpanProcessor, en plus
    de celui de ``span_exporter`` (ex. exporter aussi vers Langfuse).

    ``environment`` est posé une fois comme attribut de Resource (donc hérité
    par tous les spans sans le répéter) : convention OTel standard
    (``deployment.environment.name``), reconnue nativement par Langfuse et
    affichée comme tag de service dans Jaeger — c'est le filtre le plus
    rentable pour ne pas mélanger dev/staging/prod dans une liste de traces.
    """
    configure_logging(level)
    resource = Resource.create(
        {"service.name": service_name, "deployment.environment.name": environment}
    )

    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        SimpleSpanProcessor(span_exporter or ConsoleSpanExporter())
    )
    for exporter in extra_span_exporters or []:
        tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))

    reader = metric_reader or PeriodicExportingMetricReader(ConsoleMetricExporter())
    meter_provider = MeterProvider(resource=resource, metric_readers=[reader])

    return Telemetry(
        tracer=tracer_provider.get_tracer("mardik"),
        meter=meter_provider.get_meter("mardik"),
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
    )


def _langfuse_auth_header(public_key: str, secret_key: str) -> str:
    """Build the Basic Auth header value Langfuse expects for OTLP ingestion."""
    token = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
    return f"Basic {token}"


def _build_langfuse_span_exporter(
    host: str, public_key: str, secret_key: str
) -> SpanExporter:
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
        OTLPSpanExporter as OTLPHttpSpanExporter,
    )

    return OTLPHttpSpanExporter(
        endpoint=f"{host}/api/public/otel/v1/traces",
        headers={
            "Authorization": _langfuse_auth_header(public_key, secret_key),
            "x-langfuse-ingestion-version": "4",
        },
    )


def build_default_telemetry(
    level: str = "INFO",
    service_name: str = "mardik",
    environment: str = "development",
    langfuse_host: str = "",
    langfuse_public_key: str = "",
    langfuse_secret_key: str = "",
) -> Telemetry:
    """Production wiring: OTLP/gRPC span export to Jaeger + periodic metrics.

    Si ``langfuse_public_key``/``langfuse_secret_key`` sont fournis, les
    spans sont aussi exportés vers Langfuse (self-hébergé) en OTLP/HTTP, en
    plus de Jaeger. gRPC n'est pas supporté par Langfuse — d'où un second
    exportateur HTTP dédié.
    """
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

    extra_span_exporters: list[SpanExporter] = []
    if langfuse_public_key and langfuse_secret_key:
        extra_span_exporters.append(
            _build_langfuse_span_exporter(langfuse_host, langfuse_public_key, langfuse_secret_key)
        )

    return build_telemetry(
        span_exporter=OTLPSpanExporter(),
        metric_reader=PeriodicExportingMetricReader(ConsoleMetricExporter()),
        level=level,
        service_name=service_name,
        environment=environment,
        extra_span_exporters=extra_span_exporters,
    )


class _NoOpSpan:
    def __enter__(self) -> "_NoOpSpan":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def set_attribute(self, *args: object, **kwargs: object) -> None:
        pass


class _NoOpTracer:
    def start_as_current_span(self, *args: object, **kwargs: object) -> _NoOpSpan:
        return _NoOpSpan()


class _NoOpInstrument:
    def record(self, *args: object, **kwargs: object) -> None:
        pass

    def add(self, *args: object, **kwargs: object) -> None:
        pass


class NoOpTelemetry:
    """Telemetry that records nothing — used when observability is not wired."""

    def __init__(self) -> None:
        self.tracer = _NoOpTracer()
        self.logger = structlog.get_logger("mardik")
        self.latency_ms = _NoOpInstrument()
        self.errors = _NoOpInstrument()

    def record_latency(self, value_ms: float, **attributes: str) -> None:
        pass

    def shutdown(self) -> None:
        pass
