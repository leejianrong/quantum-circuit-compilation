"""Small-field DQI instances that build and verify in seconds with the same generator code (QCC-18).

The host verifier already takes any `(m, n, degree, r)` through `ProblemSpecDQI`, so a small instance is
the official check on a smaller code, not a re-implementation. What changes: `r` defaults to the
bent-function size for that degree, the weight distribution is recomputed, and the shot count must be
large enough for `eps_plus < 1/16` (about 1,400 shots with zero failures; `min_shots` below).

    QCC_DATA=data uv run python -m dqi_gen.instances --gen reference --instance tiny
    QCC_DATA=data uv run python -m dqi_gen.instances --gen divstep --instance medium --shots 8192

`Q2T = Q^2 * T` compares designs without the repetition factor `R`, which is large at low shot counts.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from dqi_gen import host

BATCH = 256
LOG2_DELTA = -128.0


@dataclass(frozen=True)
class Instance:
    name: str
    m: int  # codeword length, at most 2^degree - 1
    n: int  # syndromes, even
    degree: int  # field GF(2^degree)

    @property
    def t(self) -> int:
        return self.n // 2


INSTANCES = {
    i.name: i
    for i in (
        Instance("tiny", 15, 4, 4),
        Instance("small", 63, 10, 6),
        Instance("medium", 255, 20, 8),
        Instance("large", 1023, 40, 10),
        Instance("mid12", 71, 20, 12),  # degree 12 with n = 20: few degenerate events, builds in seconds
        Instance("narrow", 71, 70, 12),  # full n and field, only 71 positions: about 7M ops, fits locally
        Instance("full", 4095, 70, 12),  # the benchmark; local machines should not build it
    )
}


def min_shots(log2_delta: float = LOG2_DELTA) -> int:
    """Smallest multiple of the batch size whose zero-failure bound `eps_plus` is below 1/16."""
    need = -log2_delta / -math.log2(1 - 1 / 16)
    return math.ceil(need / BATCH) * BATCH


def build(generator: str, inst: Instance) -> Any:
    """The decoder circuit for `inst` from the named generator (`reference` or `divstep`)."""
    builders: dict[str, Callable[[int, int, int], Any]] = {}
    builders["reference"] = lambda m, n, b: host.reference().build_reference_circuit(m, n, b)

    def divstep(m: int, n: int, b: int) -> Any:
        return importlib.import_module("dqi_gen.decoder").build_circuit(m, n, b)

    builders["divstep"] = divstep

    def lanczos(m: int, n: int, b: int) -> Any:
        return importlib.import_module("dqi_gen.lanczos").build_circuit(m, n, b)

    builders["lanczos"] = lanczos

    def bm(m: int, n: int, b: int) -> Any:
        return importlib.import_module("dqi_gen.bm").build_circuit(m, n, b)

    builders["bm"] = bm

    def rs(m: int, n: int, b: int) -> Any:
        return importlib.import_module("dqi_gen.rs_build").build_circuit(m, n, b)

    builders["rs"] = rs

    def thiele(m: int, n: int, b: int) -> Any:
        return importlib.import_module("dqi_gen.thiele_decoder").build_circuit(m, n, b)

    builders["thiele"] = thiele

    def fixed(m: int, n: int, b: int) -> Any:
        return importlib.import_module("dqi_gen.fixed").build_circuit(m, n, b)

    builders["fixed"] = fixed
    if generator not in builders:
        raise ValueError(f"unknown generator {generator!r}; choose from {sorted(builders)}")
    host.verifier()  # puts kickmix on the path
    return builders[generator](inst.m, inst.n, inst.degree)


def verify(
    circuit: Any, inst: Instance, *, shots: int | None = None, salt: str = "dqi-gen-small"
) -> dict[str, Any]:
    """Official verifier on `inst`. Returns its summary plus `q2t`; raises on any failure."""
    v = host.verifier()
    shots = shots or max(2 * min_shots(), 4 * BATCH)
    if shots < min_shots():
        raise ValueError(f"{shots} shots cannot certify eps_plus < 1/16; need at least {min_shots()}")
    spec = v.ProblemSpecDQI.benchmark_instance(m=inst.m, n=inst.n, degree=inst.degree, num_shots=shots)
    out: dict[str, Any] = v.verify(circuit, spec, salt=salt.ljust(32, "x"))
    out.pop("shot_operation_counts", None)
    out["q2t"] = out["num_qubits"] ** 2 * out["toffoli_count"]
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument(
        "--gen",
        default="reference",
        choices=("reference", "divstep", "lanczos", "bm", "rs", "thiele", "fixed"),
    )
    p.add_argument("--instance", default="small", choices=sorted(INSTANCES))
    p.add_argument("--shots", type=int, default=None)
    p.add_argument("--salts", type=int, default=1, help="verify under this many salts (build once)")
    p.add_argument("--save", help="also write the circuit here as .kmb (binary)")
    p.add_argument("--sha", action="store_true", help="print the sha256 of the .kmb file")
    a = p.parse_args()
    inst = INSTANCES[a.instance]
    circuit = build(a.gen, inst)
    digest = None
    if a.sha or a.save:
        with tempfile.TemporaryDirectory() as tmp:
            path = a.save or f"{tmp}/circuit.kmb"
            circuit.to_file(path, format="kmb")
            h = hashlib.sha256()
            with open(path, "rb") as fh:
                while chunk := fh.read(1 << 24):
                    h.update(chunk)
            digest = h.hexdigest()
    keep = ("status", "num_qubits", "toffoli_count", "q2t", "score", "value_errors", "phase_errors")
    for i in range(a.salts):
        out = verify(circuit, inst, shots=a.shots, salt=f"dqi-gen-salt-{i}")
        row = {"instance": inst.name, "generator": a.gen, "salt": i, **{k: out[k] for k in keep}}
        print(json.dumps({**row, "verified_shots": out["verified_shots"], "sha256": digest}), flush=True)


if __name__ == "__main__":
    main()
