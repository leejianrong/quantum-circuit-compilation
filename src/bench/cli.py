"""`bench verify`: run the competition's own verifier and log the result to the ledger."""

import argparse
import hashlib
import importlib
import os
import pathlib
import sys
import time
from collections.abc import Callable, Sequence
from typing import Any

import numpy as np

from bench import ledger, pack

BENCHES = ("invsqrt", "dqi", "dfthcsos")
Runner = Callable[[str], float]  # salt -> official cost; raises on any verifier failure
FAILURES = (AssertionError, ValueError, RuntimeError, KeyError, OSError, EOFError)


def salt_for(i: int) -> str:
    """Deterministic 64-char salts (the metric requires at least 32). Ours, not the secret ones."""
    return hashlib.sha256(f"qcc-bench-salt-{i}".encode()).hexdigest()


def make_runner(bench: str, circuit: pathlib.Path, data: pathlib.Path, divisor: int) -> Runner:
    """Mirror the metric notebook (metric/google-quantum-ai-metric): appended sys.path, same calls."""
    sys.path += [str(data / "kickmix"), str(data / "verifiers")]
    import kickmix  # type: ignore[import-not-found,unused-ignore]

    def load(p: pathlib.Path) -> Any:
        return kickmix.Circuit.from_file(p, format=p.suffix.removeprefix("."))

    if bench == "invsqrt":
        mod = importlib.import_module("invsqrt.verify_submission_invsqrt")
        c, spec = load(circuit), mod.ProblemSpecInvSqrt.for_n_p(10)
        return lambda salt: float(mod.verify(c, spec, salt=salt)["score"])
    if bench == "dqi":
        mod = importlib.import_module("dqi.verify_submission_dqi")
        batches = max(1, mod.DEFAULT_NUM_SHOTS // mod.DEFAULT_BATCH_SIZE // divisor)
        c, spec = (
            load(circuit),
            mod.ProblemSpecDQI.benchmark_instance(num_shots=batches * mod.DEFAULT_BATCH_SIZE),
        )
        return lambda salt: float(mod.verify(c, spec, salt=salt)["score"])
    mod = importlib.import_module("dfthcsos.verify")
    files = sorted(circuit.glob("angle_k_*.km[xb]"), key=lambda p: int(p.stem.rsplit("_", 1)[1]))
    angles = [load(p) for p in files]
    with np.load(circuit / "submission.npz", allow_pickle=False) as z:
        arrays = {k: np.array(z[k]) for k in z.files}
    edges = arrays.pop("tree_edges")
    shots = max(1, mod.SHOTS_PER_ADDRESS // divisor)
    return lambda salt: float(mod.verify(angles, arrays, edges, salt=salt, shots_per_address=shots)["score"])


def run(
    bench: str, circuit: pathlib.Path, salts: int, divisor: int, runner: Callable[[], Runner]
) -> ledger.Row:
    """Verify under `salts` salts. Any exception (e.g. a corrupted circuit) is a FAIL row."""
    start = time.monotonic()
    costs: list[float] = []
    failures, error = 0, None
    try:
        verify = runner()
    except Exception as err:  # noqa: BLE001 - a bad circuit must produce a FAIL row, not a crash
        verify, failures, error = None, salts, f"load: {type(err).__name__}: {err}"
    for i in range(salts if verify else 0):
        try:
            costs.append(verify(salt_for(i)))  # type: ignore[misc]
        except FAILURES as err:
            failures, error = failures + 1, error or f"salt {i}: {type(err).__name__}: {err}"
    return ledger.Row(
        bench=bench,
        circuit=str(circuit),
        circuit_sha256=ledger.sha256_path(circuit) if circuit.exists() else "missing",
        status="FAIL" if failures or not costs else "PASS",
        cost=max(costs) if costs else None,
        costs=costs,
        shots_divisor=divisor,
        reduced_shots=divisor > 1,
        salts=salts,
        failures=failures,
        error=error,
        wall_s=round(time.monotonic() - start, 3),
        git_sha=ledger.git_sha(),
    )


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="bench")
    sub = p.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("verify", help="verify a circuit with the official verifier and log it")
    v.add_argument("bench", choices=BENCHES)
    v.add_argument("circuit", type=pathlib.Path, help="circuit file (dfthcsos: the submission directory)")
    v.add_argument("--salts", type=int, default=1)
    v.add_argument(
        "--shots-divisor", type=int, default=1, help="reduced-shot run (flagged); inner loops only"
    )
    v.add_argument(
        "--data",
        type=pathlib.Path,
        default=pathlib.Path(os.environ.get("QCC_DATA", "data")),
        help="competition data dir holding kickmix/ and verifiers/ (default $QCC_DATA or ./data)",
    )
    v.add_argument("--ledger", type=pathlib.Path, default=ledger.DEFAULT_LEDGER)
    pack.add_parser(sub)
    a = p.parse_args(argv)
    if a.cmd == "pack":
        return pack.run(a.best, a.out)
    row = run(
        a.bench,
        a.circuit,
        a.salts,
        a.shots_divisor,
        lambda: make_runner(a.bench, a.circuit, a.data, a.shots_divisor),
    )
    ledger.append(row, a.ledger)
    print(
        f"{row.status} {row.bench} cost={row.cost} failures={row.failures}/{row.salts} "
        f"sha={row.circuit_sha256[:12]} wall={row.wall_s}s" + (f" error={row.error}" if row.error else "")
    )
    return 0 if row.status == "PASS" else 1
