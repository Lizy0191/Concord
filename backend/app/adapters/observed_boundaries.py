"""Instrumentation wrappers translate metadata, not business semantics or SDK objects."""

from app.adapters.observability import Telemetry
from app.ports.services import ActionExecutor, FileStore, ReasoningEngine, WorkflowDriver


class ObservedWorkflow:
    def __init__(self, inner: WorkflowDriver, telemetry: Telemetry):
        self.inner, self.telemetry = inner, telemetry

    def begin(self, run_id: str, *, generation: int | None = None) -> str:
        with self.telemetry.span("workflow.analyze", run_id=run_id):
            return self.inner.begin(run_id, generation=generation)

    def advance(self, run_id: str, message: dict, *, generation: int | None = None) -> str:
        with self.telemetry.span("workflow.advance", run_id=run_id):
            return self.inner.advance(run_id, message, generation=generation)

    def expire(self, run_id: str, *, generation: int | None = None) -> str:
        with self.telemetry.span("workflow.expire", run_id=run_id):
            return self.inner.expire(run_id, generation=generation)

    def status(self, run_id: str) -> str:
        return self.inner.status(run_id)


class ObservedReasoning:
    def __init__(self, inner: ReasoningEngine, telemetry: Telemetry):
        self.inner, self.telemetry, self.mode = inner, telemetry, inner.mode

    def interpret(self, state, snapshot, evidence):
        with self.telemetry.span(
            "model.reasoning",
            snapshot_id=snapshot.id,
            model_role="reasoning_model",
            provider=self.mode,
            evidence_count=len(evidence),
        ):
            return self.inner.interpret(state, snapshot, evidence)

    def close(self):
        close = getattr(self.inner, "close", None)
        if close:
            close()


class ObservedExecutor:
    def __init__(self, inner: ActionExecutor, telemetry: Telemetry):
        self.inner, self.telemetry, self.mode = inner, telemetry, inner.mode

    def apply(self, state, effects, operation_id: str):
        with self.telemetry.span("action.execute", operation_id=operation_id, mode=self.mode):
            return self.inner.apply(state, effects, operation_id)

    def verify(self, before, after, effects):
        with self.telemetry.span(
            "action.verify", before_version=before.version, after_version=after.version
        ):
            return self.inner.verify(before, after, effects)


class ObservedFileStore:
    def __init__(self, inner: FileStore, telemetry: Telemetry, implementation: str):
        self.inner, self.telemetry, self.implementation = inner, telemetry, implementation

    def put(self, key, content):
        with self.telemetry.span(
            "storage.put", provider=self.implementation, bytes_count=len(content)
        ):
            return self.inner.put(key, content)

    def read(self, key):
        with self.telemetry.span("storage.read", provider=self.implementation):
            return self.inner.read(key)

    def delete(self, key):
        with self.telemetry.span("storage.delete", provider=self.implementation):
            return self.inner.delete(key)

    def health(self):
        probe = getattr(self.inner, "health", None)
        return probe() if probe else (True, "Controlled local file directory")
