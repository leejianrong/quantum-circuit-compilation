"""Write an invsqrt circuit from parameters: `python -m invsqrt_gen.cli --a 7 --frac 30,21,14 out/name`.

Writes `<prefix>.kmb` (binary) and `<prefix>.kmx` (text); the verifier hashes the canonical binary form,
so both verify identically.
"""

import argparse
import math
import pathlib
from collections.abc import Sequence

from invsqrt_gen.build import build
from invsqrt_gen.model import fit_tables, rel_error
from invsqrt_gen.params import Params
from invsqrt_gen.predict import predict
from invsqrt_gen.split import build_centered, build_split, fit_split


def parse_params(ns: argparse.Namespace) -> Params:
    frac = tuple(int(v) for v in ns.frac.split(","))
    centered = bool(getattr(ns, "centered", False))
    return Params(
        a=ns.a,
        frac=frac,
        guard=ns.guard,
        ceil=bool(getattr(ns, "split", None)) and not centered,
        centered=centered,
    )


def add_param_args(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--a", type=int, default=7, help="segment bits below the top pair (3 * 2^a entries)")
    ap.add_argument("--frac", default="30,21,14", help="fractional bits of V_0..V_d (degree = count - 1)")
    ap.add_argument("--guard", type=int, default=4, help="low bits of V_0 that are not phased")


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    add_param_args(ap)
    ap.add_argument(
        "--split",
        choices=("barrel", "serial"),
        help="split-phase generator (QCC-13) with this coarse phasing",
    )
    ap.add_argument(
        "--centered",
        action="store_true",
        help="expand about the segment middle (signed remainder); implies a split",
    )
    ap.add_argument("--passes", type=int, default=3, help="coefficient refinement passes")
    ap.add_argument("--stride", type=int, default=13, help="remainder sampling stride while fitting")
    ap.add_argument("--polish", action="store_true", help="exhaustive joint refinement of the coefficients")
    ap.add_argument("prefix", type=pathlib.Path, help="output path without extension")
    ns = ap.parse_args(argv)
    p = parse_params(ns)
    if ns.centered:
        t = fit_tables(p, passes=ns.passes, stride=ns.stride, polish=ns.polish)
        c = build_centered(p, t, ns.split or "barrel")
    elif ns.split:
        t = fit_split(p, passes=ns.passes, stride=ns.stride, polish=ns.polish)
        c = build_split(p, t, ns.split)
    else:
        t = fit_tables(p, passes=ns.passes, stride=ns.stride, polish=ns.polish)
        c = build(p, t)
    err, _ = rel_error(p, t)
    s = c.operation_statistics()
    print(f"model error 2^{math.log2(err):.2f} (budget 2^-24)")
    print(f"{c.num_qubits} qubits, {s.num_toffoli_like} Toffolis")
    print("predicted", {k: round(v, 3) for k, v in predict(p, t, c).items()})
    ns.prefix.parent.mkdir(parents=True, exist_ok=True)
    c.to_file(ns.prefix.with_suffix(".kmb"), format="kmb")
    c.to_file(ns.prefix.with_suffix(".kmx"), format="kmx")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
