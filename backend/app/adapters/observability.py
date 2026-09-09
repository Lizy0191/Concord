"""Structured logs are primary; optional OTel never exports prompts or file contents."""

import json
import logging
import time
from contextlib import contextmanager
from urllib.parse import urlsplit, urlunsplit


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "timestamp": time.time(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        fields = (
            "run_id",
            "event_id",
            "snapshot_id",
            "work_package_id",
            "operation_id",
            "provider",
            "model_role",
            "retry_count",
            "runtime",
            "latency_ms",
            "error_category",
            "request_id",
            "input_tokens",
            "output_tokens",
        )
        for field in fields:
            if hasattr(record, field):
                data[field] = getattr(record, field)
        return json.dumps(data, ensure_ascii=True)


def configure_logging() -> None:
    logger = logging.getLogger("cca")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


class Telemetry:
    """Explicit providers avoid global SDK ownership and make local tests isolated."""

    def __init__(
        self, enabled: bool = False, endpoint: str = "", *, span_exporter=None, metric_reader=None
    ) -> None:
        self.enabled = enabled
        self.available = True
        self.reason = "Disabled; structured logging remains active"
        self.traces = None
        self.metrics = None
        if not enabled:
            return
        try:
            from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.metrics import MeterProvider
            from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
        except ImportError:
            self.enabled, self.available = False, False
            self.reason = "Install the telemetry extra; core behavior is unchanged"
            return
        resource = Resource.create({"service.name": "construction-coordination-agent"})
        self.traces = TracerProvider(resource=resource, shutdown_on_exit=False)
        if span_exporter is not None:
            self.traces.add_span_processor(SimpleSpanProcessor(span_exporter))
        else:
            self.traces.add_span_processor(
                BatchSpanProcessor(
                    OTLPSpanExporter(endpoint=endpoint, timeout=3), max_queue_size=512
                )
            )
        if metric_reader is None:
            parts = urlsplit(endpoint)
            path = parts.path.removesuffix("/v1/traces").rstrip("/") + "/v1/metrics"
            metrics_endpoint = urlunsplit((parts.scheme, parts.netloc, path, "", ""))
            metric_reader = PeriodicExportingMetricReader(
                OTLPMetricExporter(endpoint=metrics_endpoint, timeout=3),
                export_interval_millis=15000,
                export_timeout_millis=4000,
            )
        self.metrics = MeterProvider(
            resource=resource, metric_readers=[metric_reader], shutdown_on_exit=False
        )
        self.tracer = self.traces.get_tracer("cca.boundaries")
        meter = self.metrics.get_meter("cca.boundaries")
        self.calls = meter.create_counter("cca.operations", unit="{operation}")
        self.duration = meter.create_histogram("cca.operation.duration", unit="s")
        self.reason = "Trace/metric exporters configured; collector reachability is not assumed"

    @contextmanager
    def span(self, name: str, **attributes):
        if not self.enabled:
            yield None
            return
        # Call sites supply only IDs/counts/roles. Never record arbitrary exception messages.
        started = time.monotonic()
        status = "ok"
        with self.tracer.start_as_current_span(
            name,
            attributes={key: value for key, value in attributes.items() if value is not None},
            record_exception=False,
            set_status_on_exception=False,
        ) as current:
            try:
                yield current
            except BaseException as exc:
                from opentelemetry.trace import Status, StatusCode

                status = "error"
                current.set_attribute("error.type", type(exc).__name__)
                current.set_status(Status(StatusCode.ERROR))
                raise
            finally:
                # Do not put high-cardinality project/operation IDs on metrics.
                labels = {"operation": name, "outcome": status}
                self.calls.add(1, labels)
                self.duration.record(time.monotonic() - started, labels)

    def close(self) -> None:
        if self.traces is not None:
            self.traces.force_flush(timeout_millis=3000)
            self.traces.shutdown()
        if self.metrics is not None:
            self.metrics.shutdown(timeout_millis=4000)
