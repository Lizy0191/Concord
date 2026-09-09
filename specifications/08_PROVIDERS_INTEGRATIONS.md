# Provider Architecture and Integration Contracts

## Provider philosophy — Frozen

External systems are data/action providers. The Construction Coordination Core must not be rewritten for a specific enterprise platform.

Prefer narrow domain-semantic Ports and adapters.

## Required provider families

At minimum implement project-owned interfaces and working demo/local adapters for:

- schedule read/write;
- workforce;
- material;
- equipment;
- inspection;
- documents;
- BIM;
- geo/GIS data;
- file/object storage;
- action execution;
- search/retrieval;
- reasoning/vision;
- durable runtime;
- resolution/optimization.

## Read/write separation

Split read and write for systems where write access is consequential. An Agent that can query schedules should not automatically receive schedule-write power.

## Demo adapters

Demo adapters are first-class contract implementations, not bypasses. They persist/reset realistic synthetic project state and simulate external confirmations/changes through the same Port contracts used by real adapters.

## Vendor adapters

Do **not** implement fake C-SMART, Procore, Autodesk, ERP, or other vendor connectors without a real accessible API contract. Instead:

- keep the provider boundary ready;
- document expected mapping points;
- optionally support interoperable standards such as IFC/BCF where appropriate;
- implement vendor connectors only when official docs/credentials are available.

This is not a failure of the final implementation; fabricating a vendor contract would be worse.

## BCF interoperability — Recommended Required Scope

Where practical, support basic BCF-compatible issue/viewpoint import/export or an adapter boundary so coordination issues can interoperate with BIM collaboration workflows. Use the published standard; do not fork/copy specification text into product code.

## Capability health

Every adapter exposes enough bootstrap/health information for the application capability page: enabled/configured, dependency loaded, service reachable when relevant, credentials present when relevant, and failure reason.

Health checks must be bounded and must not perform destructive actions.

## Contract tests

Every Provider implementation must pass shared contract tests. Fakes should model realistic failure/staleness, not only happy paths.

## Reuse rule

Use mature libraries at their natural boundary instead of vendoring/rebuilding them. Record important third-party use/version/license in repository notices.
