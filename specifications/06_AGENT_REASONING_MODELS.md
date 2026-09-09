# Agent, Reasoning, Model Roles, and Vision

## Ownership — Frozen

The project owns the coordination loop and business semantics. PydanticAI is an adapter, not the architecture.

```text
Coordination Core
      |
ReasoningEngine (project Port)
      |
+------------------------------+
|                              |
PydanticAIReasoningEngine   Offline/Demo Reasoning Path
```

## Required reasoning implementations

### PydanticAIReasoningEngine — Required

Use PydanticAI for provider/model abstraction, typed structured outputs, tool calling, scoped toolsets, and test helpers where useful. PydanticAI types do not cross the adapter boundary.

### Offline/demo reasoning — Required

Provide a deterministic offline path so the complete demo can run without cloud credentials. It may interpret structured demo events and use deterministic extraction/rules, but it must not hard-code final `READY/BLOCKED` outcomes. The same downstream Impact/Constraint/Resolution/Policy/Readiness machinery must run.

Clearly label offline/demo reasoning in UI/logs.

## Model roles

Application code references logical roles only:

- `reasoning_model`;
- `fast_model`;
- `vision_model`;
- optional `embedding_model` if semantic retrieval is enabled.

Concrete provider/model identifiers live in configuration. Do not scatter provider-specific names across business code.

## Structured outputs

All model outputs must be validated project-owned schemas. Typical reasoning outputs:

- event interpretation;
- candidate impacts;
- evidence selection/rationale;
- candidate constraints;
- resolution option descriptions;
- coordination-owner suggestions;
- document/vision extraction where uncertain.

Models do not directly persist authoritative project facts or execute actions.

## Tools and context

Build the smallest relevant context: current event, snapshot, targeted evidence, relevant work packages, allowed tools, current permission/approval context.

Tools are narrow: query dependencies, worker availability, material status, affected BIM elements, project documents, etc. Never expose arbitrary SQL/shell/network/file write.

Dynamic tool availability is determined by code based on run type, permissions, installed capabilities, and data sensitivity—not by prompt text.

## Vision — Implemented Optional

Implement a `VisionAnalyzer` adapter using the configured vision-capable model path through the reasoning/provider layer. It must:

- require explicit enablement;
- surface credential/provider availability;
- minimize/sanitize data before cloud egress;
- preserve image/document source Evidence refs;
- never autonomously turn visual interpretation into a high-risk action;
- have deterministic/fake tests that do not require a paid model in normal CI.

A real live smoke test may be opt-in when credentials are present.

## Reliability

- timeouts;
- bounded retries with exponential backoff and jitter;
- honor Retry-After when available;
- record provider/model role, request id when exposed, latency, retry count, and token/usage metadata when available;
- high-risk actions do not silently continue after model downgrade/fallback;
- provider failure cannot corrupt authoritative state.

## Model upgrades

Prefer pinned model versions/snapshots where supported. Model/provider changes must pass scenario/eval gates before becoming defaults.
