# Tauri 2 desktop host

The desktop shell reuses `../frontend` and bundles the Python API with DBOS, SQLite,
and local files. Rust supervises the sidecar, manages the per-launch connection, and
exposes an explicit native file dialog. JavaScript has no arbitrary shell or filesystem
command access. Backend startup failure is displayed, not hidden.

## Source and development build

Install the platform prerequisites from the official Tauri 2 guide: Rust and native OS
WebView development libraries; Windows also needs MSVC Build Tools and WebView2. Build
on the target operating system.

The committed locks are the normal path (not a first-checkout generation step):

```sh
# Requires uv, pnpm 10.17.1, cargo, and rustc on PATH.
python scripts/lock_dependencies.py --check
uv sync --frozen --group dev --extra desktop
pnpm --dir frontend install --frozen-lockfile
uv run --frozen --no-sync python scripts/build_desktop.py --dev

# Release-style source build:
uv run --frozen --no-sync python scripts/build_desktop.py
```

The build entry point checks all three locks, builds the Python sidecar, and uses the
frontend-owned Tauri CLI with Cargo locked. No separate installation in `desktop/` is
needed. When dependencies intentionally change, regenerate and review the affected
locks with `python scripts/lock_dependencies.py`; include manifest and lock changes
together.

On Windows, the sidecar is named `cca-sidecar-x86_64-pc-windows-msvc.exe`. The build
script derives the host triple from rustc; it does not assume Windows on Linux. Tauri
outputs platform bundles under `desktop/src-tauri/target/release/bundle`. A packaged end
user does not install Python, Node, Docker, PostgreSQL, or model keys.

Optional local parsers/solvers must first be installed through uv extras, then included
with `--feature ifcopenshell`, `--feature ortools`, or `--feature docling` when invoking
`scripts/build_desktop.py` (or `scripts/build_sidecar.py`). Docling model weights must
be staged separately for offline PDF parsing. The default offline coordination demo does
not require those features.

## Runtime boundary

The sidecar binds its own socket to `127.0.0.1:0`, prints only the allocated endpoint,
and authenticates with a fresh per-launch token passed privately by Rust. The main
webview receives that token only through a narrowly scoped native command. Native import
accepts only an explicitly selected regular file, checks extension and size before and
after reading, and sends it to the authenticated API. On exit, Rust requests a graceful
backend shutdown before killing any remaining child. Local database state lives in the
operating-system application-data directory.

## Qualification and release

Full source/integration CI and Windows native qualification, including manual Windows
installer acceptance, are established for the current team-development baseline. Build
and verify native changes on the target operating system. Linux and macOS native
qualification, code signing/notarization, and final production-release qualification
remain separate future release work. A source or target build alone does not establish a
signed, notarized, or distributable release.

See [STATUS.md](../STATUS.md) and [VERIFICATION.md](../VERIFICATION.md) for the current
verification boundary.
