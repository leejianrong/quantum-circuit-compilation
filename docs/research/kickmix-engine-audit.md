# kickmix-engine source audit (QCC-53)

Third-party code, treated as untrusted until read. Result of the audit: **nothing malicious or doubtful found**, with
the limits listed under "Could not assess". Parity with the official verifier is a separate question, covered in a follow-up note. The engine is for screening only (ADR-0001).

## What was audited

| Item | Value |
|---|---|
| Repository | https://github.com/manwithacat/kickmix-engine (Apache-2.0) |
| Pinned commit | `166b61d2e0a7404ace8acf62a6f269105e6b97f1` ("kaggle-mirror: install six alongside the kaggle CLI"), crate version 0.6.0 |
| Cloned to | `~/qcc-tools/kickmix-engine-src`, outside this repository, in an empty directory |
| Authorship | The README and source headers say it was written by an AI model under the owner's direction |

The artefact is a PyO3 extension module (`kickmix_engine._engine`, a `cdylib`) with a Python package around it, not a
standalone binary. A second workspace member, `qrom-plan`, is a chemistry planning tool with no dependencies; we did
not build or use it.

## What was checked, and what was found

Read before building anything: `Cargo.toml` (both crates), `Cargo.lock`, `pyproject.toml`, `build.sh`, the CI
workflows' headers, every Python module in `python/kickmix_engine/`, and the Rust in `src/` (8 380 lines in
`src/` and `crates/qrom-plan/src/` together). The Rust was covered by a full-text scan of every file for the patterns
below, followed by reading the call sites the scan returned and the code around every `unsafe` block.

| Question | Finding |
|---|---|
| `build.rs` in this repository | None, in either crate |
| Proc-macro crate or custom cargo config (`.cargo/`, `rust-toolchain`) | None |
| Network access in Rust (`std::net`, HTTP crates, sockets) | None |
| Process spawning in Rust | None. `qrom-plan` uses `std::thread::spawn` for threads only |
| File writes in the engine library | Only `Program::save` (the program cache, a path the caller passes) and `qrom-plan` outputs. Reads are `.kmb` files and cache files, bounds-validated on load |
| Environment reads in Rust | One: `KICKMIX_ENGINE_KERNEL` (kernel choice); `doctor` also reports its value |
| Credential, token or home-directory access | None in Rust or Python |
| `unsafe` | SIMD kernel dispatch (`avx2`/`avx512` target-feature functions, selected after CPU detection), raw-pointer writes of disjoint per-shot outputs, `get_unchecked` on opcode streams built by the program builder and re-validated when loaded from cache, `unsafe impl Send/Sync` for a pointer wrapper. Each block has a `SAFETY:` comment and is in the hot loop. None touches files, network or process state |
| Python: subprocess | One call, `cli.py`, only under `verify --cross-check`, to run the official verifier CLI. We do not use that flag |
| Python: network | One, `doctor --manifest URL` fetches a user-supplied manifest URL. We do not use `doctor --manifest` |
| Python: dynamic code | `importlib` loads the official verifier files from the path we pass (`KICKMIX_ENGINE_VERIFIERS`, our `data/verifiers/`). No `eval`, `exec` or `pickle`; `np.load(..., allow_pickle=False)` |
| Python: writes | The program cache directory (`KICKMIX_ENGINE_CACHE`, else `~/.cache/kickmix-engine`) by atomic temp file and rename; `serve` creates a mode 0600 Unix socket (not used) |

### Dependencies (`Cargo.lock`, 36 packages)

All 34 external packages come from the crates.io registry; there are no git or path dependencies other than the two
workspace crates. Direct dependencies are `pyo3 0.26`, `numpy 0.26` and `rayon 1.10`. The lock resolves to:

autocfg 1.5.1, crossbeam-deque 0.8.8, crossbeam-epoch 0.9.21, crossbeam-utils 0.8.23, either 1.19.0, heck 0.5.0,
indoc 2.0.8, libc 0.2.191, matrixmultiply 0.3.11, memoffset 0.9.1, ndarray 0.16.1, num-complex 0.4.6,
num-integer 0.1.47, num-traits 0.2.19, numpy 0.26.0, once_cell 1.21.4, portable-atomic 1.15.0,
portable-atomic-util 0.2.8, proc-macro2 1.0.107, pyo3 0.26.0, pyo3-build-config 0.26.0, pyo3-ffi 0.26.0,
pyo3-macros 0.26.0, pyo3-macros-backend 0.26.0, quote 1.0.47, rawpointer 0.2.1, rayon 1.12.0, rayon-core 1.13.0,
rustc-hash 2.1.3, rustversion 1.0.23, syn 2.0.119, target-lexicon 0.13.5, unicode-ident 1.0.27, unindent 0.2.4.

These are the well-known PyO3, ndarray and rayon trees; nothing unexpected. Several of them (`pyo3-build-config`,
`pyo3-ffi`, `libc`, `rayon-core`, `crossbeam-utils`, `portable-atomic`, `rustversion`, `proc-macro2`, `syn`, `quote`,
`target-lexicon`, `autocfg`) have build scripts or proc macros that run at build time. We did not read them.

## Build

`cargo build --release --locked -p kickmix-engine` with `CARGO_TARGET_DIR` set outside the source tree
(`~/qcc-tools/build-target`), rustc/cargo 1.97.1. It fetched the locked crates from crates.io (the only network
access, covered by the lock file checksums) and finished in 47 s. The resulting `lib_engine.so` was copied next to
a copy of the Python package under `~/qcc-tools/stage/` (a package directory with `_engine.abi3.so`; `build.sh` does
the same on macOS). No prebuilt wheel or binary from the project was installed or run.

## Could not assess

- The build scripts and proc macros of the third-party crates above (not read; mitigated by the lock file
  checksums, a pinned registry and building as an unprivileged user).
- Subtle memory-safety bugs in the `unsafe` hot loops. A malformed `.kmb` file could in principle misbehave; we only
  feed it our own circuits and mutants.
- Semantic correctness. That is established only empirically against the official verifier, per circuit.
- Whether the registry crates match their upstream repositories.

## How we run it

Only on files under a scratch directory, from a directory outside the repository, with a minimal environment
(`env -i` with `PATH`, `HOME` and the three `KICKMIX_ENGINE_*` / `PYTHONPATH` variables), no credentials. The
interpreter is the `uv sync` environment's Python with the pip `kickmix` wheel (never `data/kickmix`).
