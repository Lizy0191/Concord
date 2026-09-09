# Observability, Capability Health, and Operations

## Structured logging — Required Default

Emit structured application logs with stable correlation fields such as:

- `run_id`
- `event_id`
- `snapshot_id`
- `work_package_id`
- provider/tool/action name
- runtime
- model role/provider where safe
- latency/retry/error category
- operation_id for side effects

Never log secrets, full prompts by default, sensitive workforce data, or hidden chain-of-thought.

## OpenTelemetry — Required Implemented Optional

Instrument meaningful spans/metrics across FastAPI requests, Agent Runs/workflow phases, provider calls, model calls (metadata only), DB/storage operations, and action execution where practical.

Keep OTel API/SDK types in infrastructure/observability code. The local default must work without a collector. When OTel is disabled, application behavior is unchanged except telemetry export.

Provide an enhanced profile that can export to an OpenTelemetry collector/backend using current supported exporters. Tests must not require an external collector unless running the integration profile.

Current OpenTelemetry Python docs report stable traces and metrics, while logs remain under development; therefore prefer the project's structured logging as the log source of truth and use OTel tracing/metrics conservatively.

## Capability registry/health

Expose a non-destructive health/status endpoint and UI view that distinguishes:

- configured implementation;
- enabled/disabled;
- dependency available;
- credential present;
- external service reachable when relevant;
- healthy/unhealthy reason.

Capabilities include at least runtime, reasoning, BIM, BIM viewer, optimization, document parser, storage, database, vector retrieval, vision, GIS, observability, and desktop host (when applicable).

## Operational safety

- health checks are bounded/time-limited;
- external outages degrade only dependent capabilities;
- background workflow failures remain inspectable/retryable;
- local app remains usable when optional cloud/network capabilities are down;
- migration/startup failures fail clearly rather than silently corrupting state.

## Performance expectations

Normal dashboard/graph/document navigation should remain responsive. Heavy IFC parsing/geometry, Docling conversion, optimization, embedding, and vision tasks are background/durable operations with progress state where appropriate.

Use lazy loading for heavy frontend viewers and avoid sending massive raw project payloads to the UI or model.
