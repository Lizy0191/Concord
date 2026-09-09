# Durable Runtime, Workflows, Events, Context, and Agent Transport

## DurableRuntime — Frozen boundary

The application requires durable checkpointing, recovery, retries, waiting for approval/external state, resume, cancellation, idempotent workflow identity, and inspectable run state.

Business code must not branch on runtime vendor.

## DBOSRuntime — Required Default

Implement the default runtime using DBOS. Local/Desktop may use SQLite; server deployments may use PostgreSQL. Use DBOS workflow/step boundaries deliberately around non-deterministic or I/O work rather than wrapping every tiny function.

Use stable workflow/run ids and exploit runtime idempotency/recovery semantics where appropriate, while still enforcing application-level `operation_id` for side effects.

## TemporalRuntime — Required Implemented Optional

Implement a Temporal-backed `DurableRuntime` adapter for distributed/long-running profile use. It should support the same project-owned orchestration semantics: start/resume/status/cancel/wait/signal or equivalent capabilities required by application workflows.

Do not duplicate business logic inside Temporal workflows. Use runtime adapter/application orchestration boundaries so both runtimes execute the same coordination semantics.

If a Temporal dev service is unavailable in normal local development, keep the adapter disabled but test serialization/contracts and provide a reproducible integration profile using current official Temporal guidance.

## Core coordination workflow

The durable run must represent meaningful phases such as:

1. ingest/validate event;
2. capture snapshot;
3. collect targeted provider state/evidence;
4. reason/derive impacts;
5. compute/validate constraints and readiness;
6. generate resolution options;
7. create policy-checked ActionProposal;
8. wait for approval if required;
9. execute idempotent action;
10. verify external/result state;
11. capture fresh snapshot;
12. re-check readiness;
13. complete/fail/cancel with structured status.

Exact step granularity may vary, but state must be durable and inspectable.

## AG-UI / SSE

Use AG-UI event semantics for agent execution events rather than inventing an incompatible ad-hoc stream. Default Web/Desktop transport is HTTP/SSE from FastAPI.

Expose meaningful events for run start/status, reasoning progress, tool/provider calls at safe abstraction level, Evidence/Constraint updates, approval-needed, action result, re-check, error, and completion.

Do not leak secrets, raw prompts, chain-of-thought, or sensitive raw provider payloads into event streams.

## External waits and approvals

Approval and simulated/real external state changes must be modeled as durable workflow waits/messages/signals/events rather than busy polling in request handlers.

## Context discipline

Do not stuff the whole project into a model conversation. Derive task-specific context from the bound Snapshot and selected Evidence/providers.
