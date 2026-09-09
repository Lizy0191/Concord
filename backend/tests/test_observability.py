import json
import logging
from concurrent.futures import ThreadPoolExecutor

import pytest
from app.adapters.model_runner import ModelCallRunner
from app.adapters.observability import JSONFormatter, Telemetry


def test_structured_log_allowlist_excludes_prompt_and_secret():
    record = logging.makeLogRecord(
        {
            "msg": "Provider completed",
            "levelname": "INFO",
            "name": "cca",
            "run_id": "run-id",
            "api_key": "SECRET",
            "prompt": "PRIVATE",
        }
    )
    payload = JSONFormatter().format(record)
    assert json.loads(payload)["run_id"] == "run-id"
    assert "SECRET" not in payload and "PRIVATE" not in payload


def test_real_otel_sdk_exports_spans_and_metrics_without_collector():
    pytest.importorskip("opentelemetry.sdk")
    from opentelemetry.sdk.metrics.export import InMemoryMetricReader
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    spans = InMemorySpanExporter()
    metrics = InMemoryMetricReader()
    telemetry = Telemetry(True, span_exporter=spans, metric_reader=metrics)
    with telemetry.span("workflow.analyze", run_id="run-id"):
        with telemetry.span("model.reasoning", model_role="reasoning_model"):
            pass
    with pytest.raises(ValueError):
        with telemetry.span("provider.failure"):
            raise ValueError("PRIVATE_PAYLOAD")
    exported = spans.get_finished_spans()
    assert len(exported) == 3
    assert any(span.attributes.get("run_id") == "run-id" for span in exported)
    assert all(not span.events for span in exported)
    assert "PRIVATE_PAYLOAD" not in str(exported[-1].to_json())
    data = metrics.get_metrics_data()
    names = {
        metric.name
        for resource in data.resource_metrics
        for scope in resource.scope_metrics
        for metric in scope.metrics
    }
    assert {"cca.operations", "cca.operation.duration"} <= names
    telemetry.close()


def test_disabled_telemetry_does_not_change_behavior():
    telemetry = Telemetry(False)
    with telemetry.span("any-operation") as current:
        assert current is None
    telemetry.close()


def test_model_bridge_reuses_loop_across_worker_threads():
    import asyncio

    runner = ModelCallRunner()

    async def loop_identity():
        return id(asyncio.get_running_loop())

    with ThreadPoolExecutor(max_workers=3) as pool:
        identities = list(pool.map(lambda _: runner.call(loop_identity()), range(8)))
    assert len(set(identities)) == 1
    runner.close()
    runner.close()
