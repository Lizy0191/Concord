# READ ME FIRST — Final AI Handoff Bundle

This directory is the **authoritative implementation specification** for the final Construction Coordination Agent reference implementation. It intentionally contains **18 files** so it can be uploaded in one batch under a 20-file limit.

Do not mix this bundle with earlier baselines, bilingual human docs, or historical chat transcripts when deciding implementation behavior.

## What changed from earlier handoff drafts

Earlier drafts optimized for a first Web vertical slice and left many enhancements unimplemented. This final baseline intentionally raises the target:

- Web **and** Tauri 2 Desktop are required deliverables.
- Planned enhancement adapters must be **implemented and tested**, even when disabled by default.
- Local/Desktop must remain lightweight and runnable without cloud credentials or infrastructure services.
- Server/Team and distributed profiles must be real, reproducible configurations rather than architecture-only placeholders.

The guiding rule is:

> **Implement the capability; enable it only where the deployment profile needs it.**

## Upload / execution procedure

1. Upload all 18 Markdown files in this directory in one batch.
2. Give the coding agent access to the target repository and a terminal/code-editing environment.
3. Send the content of `17_FINAL_IMPLEMENTATION_PROMPT.md` as the first task instruction.
4. Let the agent inspect the repository, read this bundle, implement, run tests/builds, repair failures, and continue until the Definition of Done is satisfied or a genuine external blocker remains.

If there are up to two spare upload slots, use them for high-value UI reference images or one representative IFC/document fixture, not additional speculative design notes.

## Documentation status vocabulary

- **Frozen** — must not be changed without explicit user instruction.
- **Required** — must exist in the final implementation.
- **Default** — the implementation/profile used when no stronger requirement exists.
- **Implemented Optional** — must be implemented and tested, but is disabled until configured/selected.
- **External-dependent** — implementation must exist, but full live verification may require credentials or an external service; never fabricate success.

There should be almost no implementation-blocking Open decisions in this final baseline.
