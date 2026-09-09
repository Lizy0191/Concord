# Engineering Standards, Testing, CI, Dependencies, and Reuse

## Engineering contract

Frameworks serve the project; project semantics do not leak into framework-shaped architecture.

Recommended module direction:

```text
backend/app/
  domain/
  application/
  ports/
  policies/
  adapters/
  api/
```

Frontend separates domain-facing API/query code, feature/workspace UI, viewer integrations, and generic components.

## Size/cohesion guidance

Soft review thresholds:

- Python module target <= ~250 LOC; review >350; strong justification/refactor review >500.
- ordinary React/TS component target <= ~200–250 LOC; complex workspace <= ~350; review >450.
- function target <40 lines; consider split >60; >100 normally refactor.

Cohesion beats line-count gaming. Do not split one coherent algorithm into meaningless micro-files.

Avoid dumping grounds `utils.py`, `helpers.py`, `common.py`, `misc.py`.

## Dependency rules

- major new dependency requires current problem, reason, operational cost, license, and removal/replaceability story;
- prefer MIT/Apache/BSD dependencies;
- LGPL/MPL-style dependencies require careful normal dependency use rather than casual vendoring;
- AGPL/non-commercial/custom-restrictive code is not a default core dependency without explicit review;
- maintain `THIRD_PARTY_NOTICES.md` in the repository with dependency/version/license/use and whether source was modified.

Use import-linter (or equivalent enforceable mechanism) to prevent Domain/Application from importing forbidden adapter/framework layers. Use deptry or equivalent dependency hygiene tooling.

## Toolchain defaults

Backend:

- uv
- Ruff format/lint
- Pyright
- pytest
- Alembic
- import-linter
- deptry

Frontend:

- pnpm
- TypeScript checks
- linting consistent with the selected React/Vite stack
- React Testing Library/Vitest or equivalent current fit
- Playwright critical E2E

Desktop:

- Rustfmt/clippy for Tauri Rust code
- Tauri build checks

## Required test layers

1. deterministic domain unit tests;
2. repository/persistence tests on SQLite and PostgreSQL profile where practical;
3. provider shared contract tests;
4. DBOS runtime/workflow integration tests;
5. Temporal adapter contract/integration profile tests;
6. agent reasoning schema/scenario/eval tests with deterministic model/test adapters;
7. security/policy tests;
8. API tests;
9. frontend component/query tests;
10. Playwright end-to-end critical path;
11. Tauri desktop smoke/build test where current environment supports it;
12. advanced adapter tests for IfcOpenShell, OR-Tools, Docling, S3-compatible storage, pgvector, OTel, GIS, Vision.

## Critical scenarios

At minimum:

- design revision creates a real blocker;
- workforce shortage/incomplete predecessor blocks readiness;
- stale snapshot prevents action and forces refresh/recompute;
- R4 action cannot execute without required approval;
- retry does not duplicate side effects;
- clearing blockers transitions to Ready;
- malicious/untrusted document/tool content does not expand permissions;
- model/provider failure does not corrupt state;
- OR-Tools fixture returns a valid solution or explicit infeasible result;
- IFC fixture queries expected spatial/element relationships;
- document fixture preserves page/source Evidence;
- local profile starts with advanced services disabled;
- server/full profile reports missing/degraded services truthfully.

## CI

CI should run fast local checks on every change and separate heavier integration/profile jobs where practical. Do not make every PR depend on cloud model credentials.

Suggested tiers:

- `check`: formatting/lint/type/import/dependency/unit/API/frontend build;
- `test`: integration + E2E with local fixtures;
- `integration-services`: PostgreSQL/pgvector/S3/Temporal/OTel profile tests;
- `desktop`: Tauri build/smoke on supported runner(s).

## AI coding rules

- no unrelated broad refactor;
- no unrequested replacement of Frozen tech;
- no duplicate abstraction without a real second implementation or stable boundary;
- no framework types leaking into Domain/Application public contracts;
- no demo shortcuts around policy/runtime;
- no weakening tests to make CI green;
- after each coherent phase report Changed / Why / Tests / Architectural impact / remaining blockers.
