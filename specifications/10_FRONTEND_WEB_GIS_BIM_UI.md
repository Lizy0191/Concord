# Frontend, Web Application, Impact Graph, BIM, and GIS UI

## Frozen frontend stack

- React
- Vite
- TypeScript
- Tailwind CSS
- shadcn/ui
- React Flow
- TanStack Query
- pnpm

Use FastAPI OpenAPI as the source for generated TypeScript API bindings (default tool: Hey API or current compatible equivalent already selected by the project). Do not hand-maintain duplicate backend DTO interfaces when generation is practical.

## State ownership

- TanStack Query: server state/cache/invalidation;
- React local state: transient UI interactions;
- URL/router state where appropriate for navigation/shareable views;
- no Redux/Zustand by default unless a demonstrated UI-state problem requires it.

## Required views

1. project/work-package dashboard;
2. change/event workspace;
3. Impact Graph;
4. Evidence/Constraint/Resolution/Action inspector;
5. Agent Run timeline/status and approval surface;
6. documents/search surface;
7. BIM workspace;
8. GIS workspace when geo capability/data exists;
9. capability/integration status;
10. configuration/profile/about/runtime information sufficient for demo/operations.

These may be organized as one coherent workspace with panels/routes rather than ten shallow pages.

## Impact Graph

React Flow displays the **relevant subgraph**, not the entire project universe. Nodes/edges should represent domain semantics such as event, evidence/source, element/space, work package, constraint, action, and dependency. Large data sets are filtered/aggregated before rendering.

## BIM UI

Integrate That Open Engine (or the currently compatible package in that ecosystem) behind a small frontend BIM-view abstraction. Keep viewer-specific objects outside domain/server DTOs.

Support linking Impact Graph/constraint selection to BIM element highlighting where data is available.

## GIS — Required Implemented Optional

Use MapLibre GL JS for interactive maps when geo data is present. The map surface should support project/site markers/areas and selected event/work-package geometry where available. Use GeoJSON/project-owned geo DTOs at the boundary.

Do not require an external commercial tile API for the basic demo. Provide a safe local/demo style/data path or clear configuration for tiles.

## Agent streaming

Consume AG-UI-style SSE events and update run progress without blocking navigation. Reconcile final authoritative state through normal API/query invalidation after run events.

## Accessibility and performance

- keyboard-accessible common actions;
- clear focus states;
- no critical state conveyed only by color;
- virtualize/paginate large tables/lists;
- avoid unnecessary global rerenders from streaming events;
- load heavy BIM/GIS modules lazily;
- keep app usable while long model/provider calls run.

## Production build

A normal Web production build must succeed independently of Tauri. The same UI bundle/codebase is reused by desktop.

## Current MapLibre reference

MapLibre GL JS is a TypeScript/WebGL interactive map library and current v6 documentation is available at https://maplibre.org/maplibre-gl-js/docs/. Consult the current Vite/ESM guidance during implementation.
