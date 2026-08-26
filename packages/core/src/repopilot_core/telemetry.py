"""OpenTelemetry initialisation for Grafana Cloud OTLP push.

Call init_telemetry(service_name) once at process startup. When
OTEL_EXPORTER_OTLP_ENDPOINT is unset (local / CI) this is a no-op so
no extra deps are required in test environments.
"""

import structlog

logger = structlog.get_logger()


def init_telemetry(service_name: str) -> None:
    """Initialise OTel TracerProvider + MeterProvider with OTLP/HTTP exporter.

    No-op when OTEL_EXPORTER_OTLP_ENDPOINT is empty so local dev / CI runs
    clean without Grafana credentials.
    """
    from repopilot_core.settings import get_settings

    settings = get_settings()
    endpoint = settings.otel_exporter_otlp_endpoint
    if not endpoint:
        return

    try:
        from opentelemetry import metrics, trace
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource({SERVICE_NAME: f"{settings.otel_service_name}-{service_name}"})
        headers_raw = settings.otel_exporter_otlp_headers.get_secret_value()
        headers: dict[str, str] = {}
        for part in headers_raw.split(","):
            if "=" in part:
                k, _, v = part.partition("=")
                headers[k.strip()] = v.strip()

        # Tracer
        tracer_provider = TracerProvider(resource=resource)
        tracer_provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces", headers=headers))
        )
        trace.set_tracer_provider(tracer_provider)

        # Meter
        reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint=f"{endpoint}/v1/metrics", headers=headers),
            export_interval_millis=30_000,
        )
        meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
        metrics.set_meter_provider(meter_provider)

        logger.info("telemetry.init", service=service_name, endpoint=endpoint)
    except ImportError:
        logger.warning(
            "telemetry.deps_missing",
            hint="pip install opentelemetry-sdk opentelemetry-exporter-otlp-proto-http",
        )
    except Exception as exc:
        logger.warning("telemetry.init_failed", error=repr(exc))
