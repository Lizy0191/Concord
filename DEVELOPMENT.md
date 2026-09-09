# Development Guide

## Working principles

- Make focused changes; do not combine feature work with unrelated structural refactors.
- Consult `specifications/` only when a concrete change needs its detail.
- Preserve snapshot freshness, evidence traceability, approvals, permissions,
  idempotency, auditability, cancellation, and recovery guarantees.
- Fix reproducible failures before speculative changes. Never weaken tests to make
  checks pass.
- Treat executable tests and CI results as authoritative. State clearly what changed
  and what was actually verified.
- Never commit secrets, private project data, local databases, dependency directories,
  build output, caches, logs, test reports, or handoff artifacts.

For ownership boundaries and shared-file coordination, see
[TEAM_DEVELOPMENT.md](TEAM_DEVELOPMENT.md).

## Local development

Requirements: Python 3.11–3.13, uv, Node 22+, pnpm 10.17.1, and network access for
the initial dependency installation.

The committed lockfiles are the normal setup path:

```sh
uv sync --frozen --group dev
pnpm --dir frontend install --frozen-lockfile
uv run --frozen --no-sync python scripts/dev.py
```

The local workspace is loopback-only. See [README.md](README.md) for the demo and
[desktop/README.md](desktop/README.md) for native prerequisites.

The DBOS runtime uses the stable internal identity `cca` by default; this is not the
product name. Set `CCA_DBOS_APP_NAME` only when deployment isolation requires it.
Keep a chosen value stable across process restarts so durable DBOS state remains
coherent.

## Working in the refactored tree

- `frontend/src/app/**` contains application composition, workspace state, polling,
  mutation serialization, and cache reconciliation. Feature components should not
  introduce another global store.
- `frontend/src/styles.css` is the single stylesheet entry. Shared tokens and
  primitives live in `styles/base.css` and `styles/components.css`; shell, viewer,
  and feature styles own their respective selectors.
- `frontend/src/viewers/` separates BIM/GIS presentation from lifecycle hooks:
  `useIFCViewer` owns one IFC SDK lifetime, while `useBIMSource` owns source selection
  and generation-fenced reopening.
- `backend/app/adapters/persistence/*_records.py` holds repository record groups that
  share the repository transaction; record groups do not open or commit sessions.
- `backend/app/api/runs.py`, `run_events.py`, and `actions.py` split route composition,
  event streaming, and action endpoints. `backend/app/bootstrap.py` remains the
  composition root.

See [TEAM_DEVELOPMENT.md](TEAM_DEVELOPMENT.md) for the full ownership guide.

## Verification entry points

Run the smallest relevant check first, then the applicable standard suite before
review:

```sh
uv run --frozen --no-sync pytest -q backend/tests
pnpm --dir frontend test:transport
uv run --frozen --no-sync python scripts/export_openapi.py
pnpm --dir frontend typecheck
pnpm --dir frontend test
pnpm --dir frontend build
```

Use [VERIFICATION.md](VERIFICATION.md) for the CI, DBOS/Temporal, optional SDK/service,
browser, quality, and native qualification paths. The dependency-light transport suite
does not replace the React/Vitest suite or production build.

## Dependency changes

When dependencies intentionally change:

1. Update the relevant manifest.
2. Regenerate the affected lockfile(s) with `python scripts/lock_dependencies.py`.
3. Verify the complete lock set with `python scripts/lock_dependencies.py --check`.
4. Include each changed manifest and lockfile in the same review.

Do not regenerate lockfiles after cloning or as incidental cleanup. Do not hand-edit
generator-owned API artifacts (`frontend/openapi.json` and
`frontend/src/api/schema.ts`); regenerate them through the documented commands in a
locked environment.
