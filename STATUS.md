# Project Status

## Current state

The maintainability refactor is complete. Full source/integration CI qualification
passed, including the established frontend, backend, runtime, and integration gates.
Windows native qualification also passed.

A Windows installer was generated, manually installed on a real Windows machine, and
accepted after desktop startup, packaged Python sidecar and DBOS runtime operation, the
coordination demo, and application restart behavior were verified. This revision is the
intended **team-development baseline**.

The refactor separates frontend application composition, responsibility-based styles,
BIM viewer lifecycle hooks, backend repository record groups, capability preparation
and publication, and run/action/event route modules. See
[TEAM_DEVELOPMENT.md](TEAM_DEVELOPMENT.md) for ownership and shared review boundaries.

## Established qualification

- Full source/integration CI qualification passed.
- Windows native workflow qualification passed.
- Windows installer generation, installation, startup, coordination demo, packaged
  Python sidecar/DBOS runtime, and restart acceptance passed manually.

## Future release work

Linux native qualification, macOS native qualification, code signing/notarization, and
final production release qualification remain separate future release work. Product work
should continue through the team workflow in [TEAM_DEVELOPMENT.md](TEAM_DEVELOPMENT.md).
