# Desktop Application — Tauri 2

## Decision — Frozen

The final desktop host is **Tauri 2**. Do not re-open Tauri vs pywebview unless an actual blocking platform defect makes the required desktop build impossible.

Rust remains a thin desktop/OS boundary. Construction business logic and agent reasoning remain in Python.

## Required desktop architecture

```text
Tauri 2 native shell
   |
React/Vite UI (same product UI as Web)
   |
controlled local API/IPC boundary
   |
Bundled Python backend sidecar
   |
Construction Coordination Core + SQLite/DBOS/local files
```

## Python sidecar

Bundle the Python backend into a standalone executable using an appropriate current packaging method (e.g. PyInstaller or another justified compatible tool) and register it as a Tauri sidecar/external binary.

Tauri must supervise lifecycle: start on app launch, detect failure, avoid orphan processes, and stop cleanly. Use a safe dynamically selected or reserved local endpoint/IPC design; do not expose the sidecar broadly on the network.

## Tauri security

Use Tauri 2 permissions/capabilities to grant only the native commands/plugins needed by the application. Do not enable broad shell/file permissions because the UI asks for them.

File dialogs, open/save, notifications, and other native features should be narrowly scoped.

## Required desktop features

- launch and display the complete product workspace;
- automatically start/health-check the Python core;
- local project/data directory appropriate to the OS;
- open/import project documents and IFC through safe native file dialogs;
- show backend/capability startup failures clearly;
- preserve normal Web behavior where native capability is unnecessary;
- package a release bundle for the current build platform;
- include a documented path for Windows first, while keeping Tauri project cross-platform where practical.

System tray, deep links, file association, notifications, and updater may be included where they improve the product; do not let them delay core desktop correctness. If updater/signing requires release secrets, implement configuration/build wiring and document the remaining secret-dependent release step rather than inventing credentials.

## Local-first desktop profile

Desktop must not require the user to install PostgreSQL, Docker, Python, Node, Temporal, MinIO, or an LLM API key. Use SQLite + DBOS + local files by default. Advanced local capabilities (IfcOpenShell/OR-Tools/Docling) may be bundled as dependencies when packaging size/compatibility is acceptable or clearly installed as feature bundles; the UI must accurately report availability.

## Remote/server connection

It is acceptable to support a future/optional mode where the desktop UI connects to a remote server profile, but embedded local operation is required for the final reference implementation.

## Official references

Use current Tauri 2 official docs. In particular, official sidecar guidance explicitly supports bundling external binaries such as Python applications/API servers, and Tauri 2 permissions/capabilities provide scoped command access. Verify exact current configuration syntax before implementation.
