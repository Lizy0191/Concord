# User Experience, Visual Direction, and Demo Contract

## UI direction — Frozen

Design a **desktop-class engineering application**, not a marketing page, card-wall admin dashboard, or chat-first interface.

Primary layout pattern:

- persistent left project/work-package/event navigation;
- large central workspace that can switch between Impact Graph, BIM, schedule/coordination, documents, and GIS;
- right inspector for Evidence, revisions, constraints, element/work-package properties, and actions;
- bottom/top run state/timeline where appropriate;
- clear global status for current project/work package and current Agent Run.

Use React + Vite + TypeScript, Tailwind, shadcn/ui, React Flow, TanStack Query. UI code must be reusable by Web and Tauri Desktop.

## Required interaction qualities

- navigation and graph/viewer interaction remains responsive while an agent run is executing;
- long-running reasoning never blocks the whole UI;
- progressive run events arrive through AG-UI semantics, normally SSE;
- optimistic UI is allowed only for presentation state, not authoritative project facts;
- errors and degraded capabilities are visible and recoverable;
- all consequential agent conclusions link to Evidence/revisions;
- dangerous actions show risk level and approval requirement.

## Main demo fixture

Provide deterministic synthetic data representing a realistic building project with at least:

- floors/areas/work packages;
- design revisions V16/V17 (or equivalent);
- structured BIM representation plus a real small IFC fixture if license/size permits;
- schedule dependencies;
- workforce/qualification state;
- materials/equipment;
- one inspection state;
- one or more documents;
- events for design change and workforce/resource conflict.

The fixture must be seedable and resettable.

## Five-minute flow

1. Show an initially `READY` work package.
2. Inject/activate a design-change event.
3. Show Snapshot revision capture.
4. Stream run progress.
5. Show Impact Graph with affected work packages/sources.
6. Show Evidence and explicit blockers.
7. Transition to `BLOCKED`.
8. Show resolution options and one ActionProposal.
9. Require approval for an R3/R4-equivalent demonstration action as appropriate.
10. Simulate/perform the controlled external state update.
11. Re-check with a fresh Snapshot and transition to `READY` when blockers are actually cleared.
12. Run the secondary workforce/resource case using the same engine.

## Advanced capability proofs

Provide small, focused proofs without bloating the main story:

- IFC: import/query/select/highlight relevant element(s).
- OR-Tools: solve a multi-task/crew/equipment/qualification fixture and show objective/result explanation.
- Docling: parse a realistic PDF/Office document into normalized document/evidence data.
- GIS: display project/site GeoJSON and link a project/event location when geo data exists.
- Vision: analyze a safe demo image when model credentials are configured; show unavailable state otherwise.
- Desktop: run the same project workspace in Tauri.
- Server/full: capability status indicates PostgreSQL/S3/OTel/Temporal/pgvector health when enabled.

## Capability UI

Every optional/advanced capability reports one of:

- `enabled`;
- `available_disabled`;
- `unavailable_dependency`;
- `unavailable_credential`;
- `unhealthy`.

Do not equate successful import with healthy runtime integration.

## Visual quality

Prefer restrained engineering-product visual language: high information density, strong hierarchy, calm surfaces, clear status semantics, compact tables/panels, keyboard-friendly interactions, and limited decorative motion. Build a coherent workspace before adding many pages.
