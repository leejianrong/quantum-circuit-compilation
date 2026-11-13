# Static audit of syed3000's DQI builder source tree (read-only, nothing executed)

Scope: `dqi_source_zip` of the Kaggle dataset `syed3000/vqcc-own-circuit-portfolio` (Apache-2.0), 431 files: 258 Python, 130 JSON, 36 Markdown, 1
shell script (`build.sh`), 1 C++ file (`census.cpp`), 2 `.stdout` logs, LICENSE, NOTICE, SHA256SUMS. No `.so`, `.pyc`, pickle or other binary file
is in the archive. Method: `grep` over the extracted tree for the patterns below, plus reading `build.sh`, `gen_dqi.py` and the memory guard.
Nothing was run. This is a first-pass pattern scan by one reader, not a security review: it can miss obfuscated or indirect behaviour, and it
does not cover the host files (`kickmix.so`, the verifier) that `build.sh` copies in at run time.

| Check | Result |
|---|---|
| Network (`socket`, `urllib`, `requests`, `http.client`, `ftplib`, `smtplib`, `urlopen`) | none (one false positive: a variable named `overlapping_window_requests_...` in `census/validate.py`). The README states "no internet". |
| Subprocess / shell | `subprocess.run` in 8 `gen_dqi.py` variants (all spawn the same guarded child: `guard_wait.py` then `build_v7.py`, with `sys.executable`); `subprocess.Popen` in `runtime/guard.py` and `after_c5/root/guard_wait.py` (the memory guard that starts and supervises the build); `subprocess.run` in `night_c27/census/validate.py` (a census checker, not part of the build). `build.sh` runs `cp`, `mktemp`, `mv`, `rm -rf "$ROOT"` (its own temp copy), `chmod -R u+w "$ROOT"` and the Python interpreter. No `os.system`, `os.popen`, `os.exec*`. |
| `eval`, `exec`, `compile`, `__import__` | none. `importlib.import_module` with literal module names appears in 8 `check_*.py` scripts (test harnesses, not the build); `importlib.abc` in `macos_launch.py` (macOS test only: relabels the engine module's file name). |
| `pickle`, `marshal`, `shelve`, `ctypes`, `cffi` | none |
| Credentials, tokens, environment | none: no `os.environ`, `getenv`, `expanduser`, `Path.home`, `.netrc`, `.ssh`, `kaggle`, `api_key` (the word `token` is only the name of a local controller object in `rolling_tail`). `build.sh` reads `PY`, `WORK`, `KEEP_WORK`, `MAC_ENGINE`, `TMPDIR`. |
| Writes | The builder writes `dqi.kmb` and a build-log directory chosen by `--output` and `--log-directory` (`gen_dqi.py` refuses existing paths); `build.sh` writes under `$WORK` (a `mktemp -d`) and moves the result to `OUT_DIR`. The `check_*.py` scripts write JSON receipts next to themselves (not part of the build). The guard creates `/tmp/syed_dqi_heavy_job.lock` (`fcntl.flock`) and writes its JSON log. |
| Reads outside the tree | `/proc/meminfo`, `/proc/<pid>/status` (RSS of its own process group), `/sys/fs/cgroup/memory.max` and `memory.current` (memory guard). |
| Process control | `os.killpg` on the child's own process group (guard timeouts) and `signal.signal` for SIGTERM and SIGINT. |
| Absolute paths | `/usr/bin/python3.13` in `prepare_component_gates.py` and `allocation_contract.py` (these spawn checkers; the `build.sh` path uses `sys.executable`), `/tmp/syed_dqi_heavy_job.lock`, `/proc`, `/sys/fs/cgroup`. |
| `sys.path` manipulation | 65 files insert sibling directories of the tree itself (relative to `__file__`); none points outside the tree. |
| Hash pins | 113 files use `hashlib` / `sha256`. `build.sh` pins the sha256 of `kickmix.so` (`c66b3216...`) and of `verify_submission_dqi.py` (`f14274bc...`), of the output `dqi.kmb` (`7cbe8ecf...`), and checks the interpreter (CPython 3.13, not `-O`). The sources pin their own components by sha256 (130 JSON "binding", "gate" and "source review" records: the generator refuses to build when a record or a source file differs). To run it anywhere else the pins of the engine and verifier would have to be matched or edited. |

Behaviour in short: the builder is pure Python plus numpy, it starts one child process group under a memory guard, it reads only its own tree
and the two host files copied beside it, and it writes only its output and log directories plus the `/tmp` lock file. The structure is a stack
of modules patched over one another at import time (`v7_pipeline.configure` rebinds about fifteen module attributes), which makes it hard to
audit by reading; a runtime trace (strace or an import hook) in a throwaway container would be the next step if route A were considered.

Not audited: `census.cpp` (a C++ census sampler, not used by `build.sh`; compiled code would need its own review), the 130 JSON records, the
host `kickmix.so`, and the companion notebook the dataset mentions.
