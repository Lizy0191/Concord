# Final Long-Running Autonomous Implementation Prompt

Use this as the first task instruction after uploading all files in this directory.

---

You are the primary implementation agent for this repository. Treat the uploaded **Final AI Handoff Bundle** as the authoritative implementation specification.

Your task is **not** to produce another architecture plan, another document set, a scaffold, or only the first demo slice. Build the complete Construction Coordination Agent reference implementation defined by the bundle, including the Web application, Tauri Desktop application, lightweight default profile, server/team profile, and the planned advanced capability adapters.

## Start correctly

1. Read `00_READ_ME_FIRST.md` and `01_AGENTS.md` first.
2. Read every mandatory baseline document listed in `01_AGENTS.md`, then read all remaining task-specific documents before implementing the corresponding subsystem.
3. Inspect the entire existing repository, Git state, dependencies, configs, tests, and runnable entry points. Preserve correct existing work; do not assume an empty repository.
4. Create an internal dependency-aware execution plan, then **immediately implement**. Do not return only a plan if the environment permits code changes.
5. Work continuously through implementation, tests, builds, debugging, and integration until the Definition of Done below is satisfied or a genuine external blocker remains.

## Primary product loop

The real code must execute:

`ProjectEvent -> ProjectSnapshot -> Impact -> Evidence -> Constraint -> Resolution -> ActionProposal -> Policy/Approval -> Execute or simulated external update -> fresh Snapshot -> Re-check -> Ready/Blocked`

At least one independent workforce/subcontractor/process/resource scenario must reuse the same core mechanism.

Do not hard-code scenario outcomes.

## Build the full capability set

### Core / default

Implement and verify:

- React + Vite + TypeScript desktop-class Web UI;
- Tailwind + shadcn/ui;
- React Flow Impact Graph;
- TanStack Query;
- FastAPI/Pydantic application API;
- SQLAlchemy 2 + Alembic;
- SQLite local persistence;
- DBOS default durable runtime;
- local FileStore;
- structured/demo BIM provider;
- SimpleResolver;
- lightweight document parser;
- structured/FTS retrieval;
- offline deterministic demo reasoning path;
- PydanticAI `ReasoningEngine` adapter for real model use;
- REST + OpenAPI-generated TypeScript client;
- AG-UI semantics over SSE for agent run streaming;
- Snapshot/Evidence/stale protection/approval/idempotency/audit.

### Advanced implementations — must exist, not placeholders

After/alongside a stable core, implement and test:

- `ORToolsResolver` using a real constrained scheduling/resource fixture;
- `IfcOpenShellBIMProvider` using real IFC library calls and a small legal fixture or generated fixture;
- browser BIM viewer integration using That Open Engine or its current compatible package;
- `DoclingDocumentParser` with a real document fixture;
- `TemporalRuntime` adapter plus reproducible dev/integration profile;
- PostgreSQL server persistence/profile;
- `S3CompatibleFileStore` with MinIO-compatible integration profile;
- OpenTelemetry tracing/metrics export path while preserving structured logs;
- PostgreSQL `pgvector` semantic retrieval path with deterministic test embeddings and opt-in real embeddings;
- Vision analysis adapter using configured `vision_model`, disabled gracefully without credentials;
- MapLibre GIS workspace with local/demo GeoJSON data;
- Tauri 2 Desktop host with bundled/supervised Python backend sidecar and a release build path.

An advanced capability may be disabled by default, but its code must be real, independently testable, and visible in capability health/status.

## Desktop is a real deliverable

Do not leave desktop as documentation-only. Build the Tauri application using the same React UI and Python core. Keep Rust thin and limited to desktop shell, lifecycle, native permissions/capabilities, file dialogs/OS integration, and sidecar supervision.

The Desktop local profile must run without installing PostgreSQL, Docker, Python, Node, Temporal, MinIO, or cloud-model credentials on the end-user machine after packaging.

If the current environment cannot produce a release binary for every OS, produce and verify the current-platform build and keep cross-platform Tauri configuration sane. Report unavailable platform-specific signing/build verification precisely.

## Zero-friction startup

Provide a low-friction local developer/demo startup path. Prefer one documented command (or one command per Web/Desktop mode) that initializes/migrates local state, seeds demo data when requested, and starts required processes.

The default local demo must not require PostgreSQL, Docker, Temporal, MinIO, an OTel collector, an external construction system, or an LLM API key.

Real model/provider capabilities are enabled through environment/configuration. Offline/demo mode must be clearly labeled.

## Profiles

Implement explicit configuration profiles equivalent to:

- Local Web;
- Desktop;
- Server/Team;
- Full/Distributed.

Avoid scattering `if profile == ...` throughout business logic. Profiles select adapters/bootstrap/configuration behind Ports.

## Security / action rules

Never weaken these to complete the demo:

- LLM output is a Proposal only.
- Side effects go through Schema, Permission, Business Rule, Snapshot freshness, Approval, Idempotency, Execute, Verify, Audit.
- No arbitrary SQL/shell/network/file-write tools.
- Untrusted document/IFC/tool content cannot expand permissions.
- R3/R4 actions require the documented human approval level.
- R5 remains prohibited.
- Sensitive data is minimized before external model egress.

## Reuse instead of rebuilding

Use mature third-party capabilities at their natural boundaries. Consult current official docs and examples. Do not rebuild ORM, workflow engines, IFC parsing, BIM rendering, document parsing, optimization solvers, vector search, map rendering, agent transport protocols, or desktop shell infrastructure from first principles.

Maintain third-party notices with current version/license/use. Do not copy incompatible/restrictive code into the repository merely because an example is convenient.

## Testing and verification

Run tests continuously and fix root causes. Do not make suites green by deleting meaningful tests, weakening assertions, bypassing policy, or replacing real integration code with placeholders.

At minimum verify:

1. design change creates a real Evidence-backed blocker;
2. workforce/resource/predecessor conflict uses the same core;
3. stale Snapshot blocks action and triggers refresh/recompute;
4. R4 action cannot execute without strong approval;
5. retry cannot duplicate a side effect;
6. clearing blockers yields `READY` only after a fresh re-check;
7. untrusted content cannot expand tools/permissions;
8. model/provider failure cannot corrupt authoritative state;
9. OR-Tools solves or reports infeasibility for a real fixture;
10. IfcOpenShell queries expected element/spatial data;
11. Docling parsing preserves source/page Evidence;
12. local profile starts with no external infrastructure;
13. PostgreSQL profile works and migrations pass;
14. S3-compatible storage adapter passes integration tests when service is available;
15. Temporal adapter passes contract/integration tests when service is available;
16. OTel emits/export path works when enabled without becoming a local requirement;
17. pgvector retrieval works in the server integration profile;
18. GIS view renders demo geo data;
19. Vision capability fails closed/disabled without credentials and can run an opt-in live smoke test with credentials;
20. Web production build succeeds;
21. Playwright covers the critical demo path;
22. Tauri Desktop dev/build path succeeds on the available platform and launches the Python core correctly;
23. architecture/import/dependency checks enforce framework boundaries.

## External-service rule

If a live service/credential is genuinely unavailable:

- do not remove the implementation;
- do not fabricate a passing live test;
- implement against current official APIs;
- provide deterministic contract tests/fakes where appropriate;
- provide a reproducible integration profile/command;
- run everything the environment can run;
- record exactly what remains unverified and why.

Continue all independent work instead of stopping early.

## Definition of Done

Do not call the project complete until:

- the Web product is runnable and interactive;
- the Tauri Desktop product is runnable/buildable on the current platform;
- the main and secondary coordination scenarios work end to end through formal layers;
- Snapshot, Evidence, stale protection, approval, idempotency, and audit are observable on the critical path;
- all Required advanced adapters above contain real implementations and tests, not TODOs/stubs;
- the local default remains zero-infrastructure and credential-optional;
- server/full profiles are reproducible and truthfully health-checked;
- key UI includes project/work packages, event/change flow, Impact Graph, Evidence/constraints/actions, Agent timeline, approval, BIM, GIS when applicable, and capability status;
- generated API client and frontend/backend schemas are synchronized;
- relevant lint/type/unit/integration/E2E/architecture/build checks pass;
- README/run/demo instructions allow another developer to start and demonstrate the system;
- third-party reuse/license information is recorded;
- no demo shortcut bypasses the architecture or safety rules.

## Final report

When complete, report concisely but precisely:

1. **What was built** — Web, Desktop, core flows, advanced capabilities.
2. **Architecture realized** — modules, runtime/profile selection, data flow.
3. **How to run** — shortest commands for Local Web, Desktop, Server/Full profiles.
4. **Five-minute demo** — exact click/run sequence.
5. **Capability matrix** — enabled/default/available/unavailable and health.
6. **Verification actually executed** — commands and results, separating live vs deterministic tests.
7. **Desktop build status** — exact artifact/build/platform status.
8. **Third-party reuse/licenses**.
9. **Known limitations / external blockers** — only genuine ones, no hidden failures.
10. **Recommended next work** — only after the complete baseline is actually finished.

Begin now. Do not reply with only a plan. Read the bundle and repository, then implement, test, build, repair, and continue until the complete final baseline is satisfied or a genuine external blocker prevents further safe progress.
