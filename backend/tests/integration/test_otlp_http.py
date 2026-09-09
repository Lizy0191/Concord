"""Exercises installed OTel SDK/exporters over real loopback HTTP, not a collector mock API."""

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from app.adapters.observability import Telemetry


def test_real_otlp_http_exports_trace_and_metric_payloads():
    pytest.importorskip("opentelemetry.sdk")
    pytest.importorskip("opentelemetry.exporter.otlp.proto.http")
    from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import (
        ExportMetricsServiceRequest,
    )
    from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

    received = []

    class Receiver(BaseHTTPRequestHandler):
        def do_POST(self):
            received.append((self.path, self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(200)
            self.send_header("Content-Type", "application/x-protobuf")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Receiver)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    telemetry = Telemetry(True, f"http://127.0.0.1:{server.server_port}/v1/traces")
    try:
        with telemetry.span("action.execute", operation_id="synthetic-operation", runtime="test"):
            pass
        assert telemetry.traces.force_flush(timeout_millis=3000)
        assert telemetry.metrics.force_flush(timeout_millis=3000)
    finally:
        telemetry.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    traces = [
        ExportTraceServiceRequest.FromString(body)
        for path, body in received
        if path == "/v1/traces"
    ]
    metrics = [
        ExportMetricsServiceRequest.FromString(body)
        for path, body in received
        if path == "/v1/metrics"
    ]
    assert traces and metrics
    spans = [
        span
        for export in traces
        for resource in export.resource_spans
        for scope in resource.scope_spans
        for span in scope.spans
    ]
    assert any(span.name == "action.execute" for span in spans)
    names = {
        metric.name
        for export in metrics
        for resource in export.resource_metrics
        for scope in resource.scope_metrics
        for metric in scope.metrics
    }
    assert {"cca.operations", "cca.operation.duration"} <= names
    for _, body in received:
        assert b"Bearer" not in body
        assert b"prompt" not in body
