# Domain, Persistence Semantics, Snapshot, and Evidence

## Core domain objects — Required

At minimum define project-owned models for:

- `Project`
- `Area` / `Location` as needed
- `WorkPackage`
- `ProjectEvent`
- `ProjectSnapshot`
- `SourceRevision`
- `Evidence`
- `Finding`
- `Impact`
- `Constraint`
- `ResolutionOption`
- `ActionProposal`
- `Approval`
- `ActionExecution`
- `AgentRun`
- `AuditRecord`
- provider/capability status objects

Names may vary slightly only when semantics remain clear.

## WorkPackage readiness

Readiness is explicit, explainable domain state, not a model free-text answer. A work package is `BLOCKED` when unresolved blocking Constraints exist under current authoritative state. It becomes `READY` only after blockers are cleared and re-checked against a fresh enough snapshot.

Readiness rules must be deterministic and tested.

## ProjectSnapshot — Frozen

Every material analysis/run binds to a snapshot of relevant source revisions/observation times, for example:

- drawing/document revision;
- BIM revision/hash;
- schedule revision;
- material revision/observed_at;
- inspection revision/observed_at;
- workforce observed_at;
- equipment observed_at;
- other provider-specific version tokens.

Snapshots are immutable records. Before a consequential side effect, revalidate all relevant revision tokens. Any meaningful mismatch yields `STALE_RESULT`/`StaleSnapshotError`, aborts execution, refreshes source data, and recomputes.

## Evidence — Frozen

Consequential Findings/Constraints must be explainable by persisted Evidence. Evidence includes enough information to trace origin without requiring the original model conversation:

- source/provider;
- source identifier/path/object id;
- source revision/hash;
- observed_at;
- location/page/element/work-package reference where applicable;
- extracted fact/snippet or structured fact;
- confidence/quality metadata when appropriate.

A Finding should expose conclusion, evidence refs, snapshot id, reasoning summary, confidence, limitations, and timestamps.

## Persistence mapping

Use Pydantic/project-owned domain/contracts separately from SQLAlchemy ORM models. Do not turn one class into API + domain + database + agent schema simultaneously.

Use explicit mapper/repository functions where needed; avoid a generic repository abstraction that hides all semantics.

## IDs and time

- stable opaque IDs (UUID/ULID or similarly robust choice) for domain entities and operation ids;
- timezone-aware UTC timestamps in persisted/API data;
- human UI localizes presentation only;
- content/revision hashes may supplement source revision ids.

## Audit

Persist meaningful state transitions, approvals, action attempts/results, model/provider identity metadata, snapshot associations, and capability/runtime decisions. Audit data is append-oriented and must not rely on model chat transcript as the only record.

## Demo data

Synthetic fixture data is allowed and required for deterministic demos, but it must enter through provider/repository contracts. Do not special-case final outcomes by event id.
