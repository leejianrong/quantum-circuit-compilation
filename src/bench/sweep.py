"""`bench sweep`: build a circuit for every point of a parameter grid and verify each one (QCC-52).

The generator is any command line with `{name}` placeholders and one `{out}` placeholder, for example
`python scripts/my_gen.py --window {w} --guard {g} --out {out}`. Each point is built, then verified under an
exclusive file lock (`flock /tmp/qcc-heavy.lock` semantics) so two sweeps, or a sweep and a hand-run verify
that uses the same lock, never run heavy jobs at once. One ledger row per point, plus a resumable sweep log
(`<out-dir>/sweep.jsonl`) that keeps the parameters, which the ledger has no field for.
"""

import argparse
import fcntl
import hashlib
import itertools
import json
import os
import pathlib
import random
import shlex
import subprocess
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from bench import experiments, ledger

HEAVY_LOCK = pathlib.Path("/tmp/qcc-heavy.lock")  # the lock the docs already use with `flock`
Point = dict[str, str]
Verify = Callable[[pathlib.Path, Point], ledger.Row]


@contextmanager
def heavy_lock(path: pathlib.Path = HEAVY_LOCK) -> Iterator[None]:
    """Block until we hold the exclusive heavy-verify lock; same lock file as `flock` on the command line."""
    with path.open("a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def parse_param(spec: str) -> tuple[str, list[str]]:
    """`w=4,5,6` -> values as given; `w=4:8` or `w=4:12:2` -> an inclusive integer range."""
    name, sep, vals = spec.partition("=")
    if not sep or not name.isidentifier() or not vals:
        raise ValueError(f"bad parameter {spec!r}: use name=v1,v2 or name=lo:hi[:step]")
    if ":" in vals:
        lo, hi, *step = (int(x) for x in vals.split(":"))
        if len(step) > 1 or (step and step[0] < 1) or hi < lo:
            raise ValueError(f"bad range in {spec!r}")
        return name, [str(x) for x in range(lo, hi + 1, step[0] if step else 1)]
    return name, vals.split(",")


def make_points(
    params: dict[str, list[str]], mode: str = "grid", n: int | None = None, seed: int = 0
) -> list[Point]:
    """Every grid point in a stable order, or `n` of them sampled without replacement (seeded)."""
    names = sorted(params)
    grid = [dict(zip(names, vals, strict=True)) for vals in itertools.product(*(params[k] for k in names))]
    if mode == "random":
        if not n or n < 1:
            raise ValueError("random mode needs --n >= 1")
        return random.Random(seed).sample(grid, min(n, len(grid)))
    return grid[:n] if n else grid


def point_id(p: Point) -> str:
    return hashlib.sha256(json.dumps(p, sort_keys=True).encode()).hexdigest()[:10]


def render(template: str, p: Point, out: pathlib.Path) -> list[str]:
    """Split the template first, then fill each token, so values never get re-parsed by a shell."""
    return [tok.format(out=out, **p) for tok in shlex.split(template)]


def read_log(path: pathlib.Path) -> dict[str, dict[str, Any]]:
    done: dict[str, dict[str, Any]] = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if line:
                rec = json.loads(line)
                done[rec["point"]] = rec
    return done


def run_sweep(
    template: str,
    points: list[Point],
    out_dir: pathlib.Path,
    verify: Verify,
    *,
    suffix: str = ".kmb",
    ledger_path: pathlib.Path = ledger.DEFAULT_LEDGER,
    lock_path: pathlib.Path = HEAVY_LOCK,
    build_timeout: float = 3600.0,
    rerun: bool = False,
) -> list[dict[str, Any]]:
    """Build and verify each point not already in the sweep log. Returns the records of this run."""
    out_dir.mkdir(parents=True, exist_ok=True)
    log = out_dir / "sweep.jsonl"
    done = read_log(log)
    records: list[dict[str, Any]] = []
    for p in points:
        pid = point_id(p)
        if pid in done and not rerun:
            continue
        circuit = out_dir / f"{pid}{suffix}"
        rec: dict[str, Any] = {"point": pid, "params": p, "circuit": str(circuit), "ts": ledger.now()}
        try:
            proc = subprocess.run(  # noqa: S603 - argv list from a user-supplied template, no shell
                render(template, p, circuit),
                capture_output=True,
                text=True,
                timeout=build_timeout,
                check=False,
            )
            built = proc.returncode == 0 and circuit.exists()
            err = None if built else f"build rc={proc.returncode}: {proc.stderr.strip()[-300:]}"
        except (subprocess.TimeoutExpired, OSError, KeyError, IndexError, ValueError) as e:
            built, err = False, f"build: {type(e).__name__}: {e}"
        if not built:
            rec.update(status="BUILD_FAIL", error=err, cost=None, failures=None, sha=None)
        else:
            with heavy_lock(lock_path):
                row = verify(circuit, p)
            ledger.append(row, ledger_path)
            rec.update(
                status=row.status,
                cost=row.cost,
                failures=row.failures,
                sha=row.circuit_sha256,
                wall_s=row.wall_s,
                reduced_shots=row.reduced_shots,
                error=row.error,
            )
        with log.open("a") as f:
            f.write(json.dumps(rec, sort_keys=True) + "\n")
        records.append(rec)
    return records


def ranking(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """PASS points, cheapest first (cost is already the worst over the salts)."""
    return sorted(
        (r for r in records if r["status"] == "PASS" and r["cost"] is not None), key=lambda r: r["cost"]
    )


def add_parser(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    p = sub.add_parser("sweep", help="build and verify a generator over a parameter grid (heavy lock held)")
    p.add_argument("bench", choices=("invsqrt", "dqi", "dfthcsos"))
    p.add_argument("--gen", required=True, help="generator command with {name} placeholders and {out}")
    p.add_argument("--param", action="append", default=[], metavar="NAME=V1,V2|LO:HI[:STEP]", required=True)
    p.add_argument("--mode", choices=("grid", "random"), default="grid")
    p.add_argument("--n", type=int, help="grid: first n points; random: sample size")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out-dir", type=pathlib.Path, required=True)
    p.add_argument("--suffix", default=".kmb", help='output name suffix; "" for a dfthcsos directory')
    p.add_argument("--salts", type=int, default=1)
    p.add_argument("--shots-divisor", type=int, default=1, help="reduced-shot screen (flagged)")
    p.add_argument("--experiment", help="experiment id the rows belong to")
    p.add_argument("--build-timeout", type=float, default=3600.0)
    p.add_argument("--lock", type=pathlib.Path, default=HEAVY_LOCK)
    p.add_argument("--rerun", action="store_true", help="redo points already in the sweep log")
    p.add_argument("--dry-run", action="store_true", help="print the commands, build nothing")
    p.add_argument("--ledger", type=pathlib.Path, default=ledger.DEFAULT_LEDGER)
    p.add_argument("--experiments", type=pathlib.Path, default=experiments.DEFAULT_LOG)
    p.add_argument("--data", type=pathlib.Path, default=pathlib.Path(os.environ.get("QCC_DATA", "data")))
    p.add_argument("--top", type=int, default=5, help="rows in the closing table")


def dispatch(a: argparse.Namespace, verify_factory: Callable[[argparse.Namespace], Verify]) -> int:
    try:
        params = dict(parse_param(s) for s in a.param)
        points = make_points(params, a.mode, a.n, a.seed)
    except ValueError as err:
        print(f"error: {err}")
        return 2
    if a.dry_run:
        for p in points:
            print(
                point_id(p),
                " ".join(shlex.quote(t) for t in render(a.gen, p, a.out_dir / (point_id(p) + a.suffix))),
            )
        return 0
    records = run_sweep(
        a.gen,
        points,
        a.out_dir,
        verify_factory(a),
        suffix=a.suffix,
        ledger_path=a.ledger,
        lock_path=a.lock,
        build_timeout=a.build_timeout,
        rerun=a.rerun,
    )
    best = ranking(records)
    print(f"{len(records)} points run ({len(points) - len(records)} already done), {len(best)} PASS")
    for r in best[: a.top]:
        print(f"{r['cost']:.6g}\t{r['point']}\t{json.dumps(r['params'], sort_keys=True)}")
    return 0 if records and not all(r["status"] == "BUILD_FAIL" for r in records) else 1
