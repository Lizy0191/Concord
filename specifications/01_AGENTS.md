# AI Implementation Entry Point

> Read this file first. It is the execution contract and document map.

## Mission

Build the complete **Construction Coordination Agent** reference implementation: a local-first construction coordination and constraint-removal application that turns project change into traceable impacts, constraints, resolutions, controlled actions, and readiness re-checks.

Invariant loop:

`Event -> Impact -> Constraint -> Resolution -> Action -> Re-check`

The finished product is not a chatbot, not a generic project-management suite, and not an architecture-only proof.

## Authority

When personal implementation preference conflicts with this bundle, follow this bundle.

Priority:

1. explicit current user instruction;
2. Frozen decisions in this bundle;
3. Required/Default implementation decisions;
4. consolidated decisions in `16_DEPLOYMENT_PROFILES_DECISIONS.md`;
5. general prose.

If current third-party APIs differ from an example, consult current official documentation and make the smallest compatible adjustment without changing project-owned boundaries. Record the adjustment.

## Mandatory first read

Before meaningful implementation read:

1. `02_PRODUCT_REQUIREMENTS.md`
2. `03_USER_EXPERIENCE_AND_DEMO.md`
3. `04_SYSTEM_ARCHITECTURE.md`
4. `05_DOMAIN_DATA_SNAPSHOT_EVIDENCE.md`
5. `13_SECURITY_PRIVACY_ACTIONS.md`
6. `15_ENGINEERING_TESTING_CI.md`
7. `16_DEPLOYMENT_PROFILES_DECISIONS.md`

Then route by task:

| Work | Read |
|---|---|
| Product/UI/demo | `02`, `03`, `10` |
| Domain/persistence/snapshot/evidence | `05`, `12` |
| Agent/LLM/vision | `06` |
| DBOS/Temporal/events/context/tools | `07` |
| Provider interfaces/integrations | `08` |
| IFC/Docs/OR-Tools | `09` |
| Frontend/BIM/GIS | `10` |
| Tauri/Desktop | `11` |
| Storage/retrieval/Postgres/pgvector | `12` |
| Security/approval/privacy | `13` |
| OTel/operations/capability health | `14` |
| Tests/CI/dependencies/licenses | `15` |
| Profiles/decision rationale | `16` |

## Non-negotiable invariants

1. Database/domain state is authoritative; LLM/chat/UI state is not.
2. Material analysis binds to `ProjectSnapshot`; consequential Findings cite Evidence.
3. Relevant revisions are revalidated before side effects; stale results stop and recompute.
4. LLM output is a structured Proposal only.
5. Side effects pass through `Schema -> Permission -> Business Rule -> Snapshot -> Approval -> Idempotency -> Execute -> Verify -> Audit`.
6. Domain/Application public contracts do not import peripheral framework types.
7. No arbitrary SQL, shell, unrestricted network, or unrestricted file-write tools are exposed to the agent.
8. Numeric constraints, permissions, geometry, scheduling, and readiness rules are deterministic code/tool responsibilities.
9. Demo data may be synthetic; final outcomes must not be hard-coded.
10. Advanced adapters must be real implementations, not empty interfaces, but the local default profile remains lightweight.
11. Never make PostgreSQL, Temporal, MinIO, OTel collector, cloud LLM credentials, or a dedicated service mandatory for local demo startup.
12. Do not fake vendor integrations when no real API contract/credential exists.

## Implementation posture

The strong coding agent is authorized to keep progressing autonomously inside these boundaries. Do not stop at plans, scaffolds, TODOs, placeholder adapters, or mock-only screens if the environment permits implementation.

Use vertical integration milestones, but continue past the first slice until the full final Definition of Done in `17_FINAL_IMPLEMENTATION_PROMPT.md` is satisfied.

When an external integration cannot be live-verified because credentials/service/runtime are unavailable:

- implement the adapter against the real documented API/library;
- add contract/unit tests and a deterministic fake where appropriate;
- add a health check and explicit capability state;
- add a reproducible integration-test/profile path;
- report live verification as unavailable, never as passed.
