# Security, Privacy, Permissions, and Side Effects

## Fail-safe architecture — Frozen

Reasoning output is always a Proposal, never a command.

Side-effect chain:

`Proposal -> Schema -> Permission -> Business Rule -> Snapshot Freshness -> Approval -> Idempotency -> Execute -> Verify -> Audit`.

No layer may skip the chain merely because the demo would be easier.

## Action risk levels

| Level | Examples | Default policy |
|---|---|---|
| R0 | read/query project data | automatic |
| R1 | analysis/recommendation/finding | automatic |
| R2 | create internal issue/draft task | automatic or light approval |
| R3 | schedule change, workforce move, subcontractor notification | human approval |
| R4 | stop-work, procurement, payment, formal BIM modification | mandatory strong human approval |
| R5 | legal liability/final safety judgment | prohibited |

## Idempotency

Every side-effecting operation has a stable `operation_id`. Retries after a successful side effect must return/reconcile the original result rather than re-execute.

## Prompt/tool injection

Treat documents, model content, web/provider responses, IFC metadata, and tool outputs as untrusted content. They cannot expand permissions or tool availability.

Tool capability is selected by code/policy, not prompt instructions embedded in source content.

## Tool restrictions

Never expose arbitrary SQL, unrestricted shell, unrestricted network calls, arbitrary file-system writes, or generic “call any API” functionality to the agent.

## Data minimization and LLM egress

Before cloud model calls:

- select only relevant fields/evidence;
- de-identify/minimize workforce data;
- exclude government IDs, phone numbers, biometrics/faces, full personnel trajectories, and irrelevant sensitive commercial/contract data by default;
- record data category/provider/model role where appropriate;
- make Vision/full-document cloud upload explicit and visible.

BIM/documents should remain local whenever model reasoning can use extracted/selected evidence instead of uploading entire project files.

## Desktop security

Tauri native permissions/capabilities must be narrowly scoped. The Python sidecar binds only to an appropriate local interface/IPC and validates requests/authenticity as appropriate for the chosen local transport. Do not assume WebView content is trusted merely because it is local.

## Server security

Do not expose the server/team profile publicly with an implicit “demo trust” model. If full identity/auth is outside the competition-facing scope, clearly bind to trusted/internal deployment and document the requirement for authentication/reverse-proxy/identity integration before Internet exposure. Never fabricate enterprise identity integration.

## Secrets

Use environment/config secret injection; commit `.env.example`, never real credentials. Tauri signing/updater keys, model keys, S3 credentials, and external service tokens stay outside source control.

## Audit and privacy tests

Test stale-action blocking, risk approval, duplicate-retry prevention, injection not expanding tools, sensitive-field filtering, path/object-key safety, and provider/model failure not corrupting authoritative state.
