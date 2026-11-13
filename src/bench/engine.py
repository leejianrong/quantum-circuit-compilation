"""Opt-in screening through the third-party kickmix-engine (`bench verify --engine kickmix-engine`).

The engine is a faster re-implementation of the official verifier flow. It is for screening only: ADR-0001
says the official verifier gates promotion, so every row made here is `kind=screen`, carries an `engine` tag
with the engine's commit, and `bench promote` ignores such rows. The engine is never imported; it runs as a
subprocess with an allowlisted environment (no tokens).

Setup (see docs/MEASUREMENT.md): build it from the audited commit, then
    QCC_KICKMIX_ENGINE=/path/to/launcher   an executable that takes `verify <bench> <circuit> --salt S ...`
    QCC_KICKMIX_ENGINE_SHA=<commit>        the commit it was built from, recorded on every row
"""

import json
import os
import pathlib
import subprocess
from collections.abc import Callable, Mapping

ENV_BIN = "QCC_KICKMIX_ENGINE"
ENV_SHA = "QCC_KICKMIX_ENGINE_SHA"
NAME = "kickmix-engine"
PASS_ENV = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "PYTHONPATH", "QCC_DATA")


def settings(environ: Mapping[str, str] | None = None) -> tuple[pathlib.Path, str]:
    """The engine launcher and its commit SHA, from the environment; raises RuntimeError if unset."""
    environ = os.environ if environ is None else environ
    path, sha = environ.get(ENV_BIN, ""), environ.get(ENV_SHA, "").strip()
    if not path or not pathlib.Path(path).is_file() or not os.access(path, os.X_OK):
        raise RuntimeError(f"set {ENV_BIN} to the built kickmix-engine launcher (docs/MEASUREMENT.md)")
    if not sha:
        raise RuntimeError(f"set {ENV_SHA} to the commit the engine was built from; rows record it")
    return pathlib.Path(path), sha


def tag(sha: str) -> str:
    return f"{NAME}@{sha[:12]}"


def child_env(data: pathlib.Path, environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """Allowlisted environment for the engine process: no credentials pass through."""
    environ = os.environ if environ is None else environ
    env = {k: v for k, v in environ.items() if k in PASS_ENV or k.startswith("KICKMIX_ENGINE_")}
    env.setdefault("KICKMIX_ENGINE_VERIFIERS", str(data / "verifiers"))
    return env


def make_runner(
    bench: str,
    circuit: pathlib.Path,
    data: pathlib.Path,
    *,
    threads: int | None = None,
    environ: Mapping[str, str] | None = None,
) -> Callable[[str], float]:
    """salt -> the engine's `score`. A reported FAIL raises AssertionError with the engine's message."""
    binary, _ = settings(environ)
    env = child_env(data, environ)

    def run(salt: str) -> float:
        cmd = [str(binary), "verify", bench, str(circuit.resolve()), "--salt", salt]
        if threads:
            cmd += ["--threads", str(threads)]
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env, check=False)
        try:
            out = json.loads(proc.stdout)
        except ValueError:
            raise RuntimeError(f"engine gave no JSON (rc={proc.returncode}): {proc.stderr[-300:]}") from None
        if out.get("status") != "PASS":
            raise AssertionError(out.get("error") or f"engine status {out.get('status')}")
        return float(out["score"])

    return run
