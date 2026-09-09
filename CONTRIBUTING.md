# Contributing

Read [README.md](README.md), [DEVELOPMENT.md](DEVELOPMENT.md), relevant parts of
[VERIFICATION.md](VERIFICATION.md), and [TEAM_DEVELOPMENT.md](TEAM_DEVELOPMENT.md) before
starting work.

## Workflow

Normal feature and bug work starts with an Issue. Create a short-lived issue branch from
`main`, keep the change focused, and integrate through a pull request only—never direct
feature pushes to `main`. Use `Closes #<issue>` in the PR description.

Normal PRs need one peer approval, applicable CI, and resolved review conversations.
High-risk shared seam changes need stronger review as described in
[TEAM_DEVELOPMENT.md](TEAM_DEVELOPMENT.md). Coordinate before editing a shared contract
or seam; one active owner should change it at a time.

## Change hygiene

Preserve snapshot freshness, evidence traceability, approvals, permissions, idempotency,
auditability, cancellation, and recovery. Run the smallest relevant checks, then the
broader checks required by the affected area. Report commands and results; if a check
cannot run locally, state the command, blocker, and remaining qualification.

`frontend/openapi.json` and `frontend/src/api/schema.ts` are generator-owned. Regenerate
them only through the documented locked commands; never hand-edit them. Use committed
locks for normal work and do not make incidental manifest or lockfile updates.

Do not submit secrets, private project data, local databases, dependency directories,
build output, caches, logs, test reports, or handoff artifacts. Keep `.env.example` safe
and preserve notices for approved third-party material.
