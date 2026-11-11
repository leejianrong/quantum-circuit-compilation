"""Experiment log: `bench exp new|close|list`, stored in ledger/experiments.jsonl (docs/MEASUREMENT.md).

Append-only. Each line is a full snapshot of one experiment; the last line for an id wins, so closing
an experiment appends a new line rather than rewriting history.
"""

import argparse
import json
import pathlib
from dataclasses import asdict, dataclass

from bench import ledger

DEFAULT_LOG = pathlib.Path("ledger/experiments.jsonl")
OUTCOMES = ("promoted", "rejected", "failed", "abandoned")


@dataclass
class Experiment:
    id: str
    hypothesis: str
    benchmark: str
    parent: str | None  # circuit sha256 the change starts from
    status: str  # "open" or "closed"
    opened: str
    outcome: str | None = None
    notes: str | None = None
    closed: str | None = None


def read(path: pathlib.Path = DEFAULT_LOG) -> dict[str, Experiment]:
    """Latest snapshot per id, in first-seen order."""
    out: dict[str, Experiment] = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if line:
                e = Experiment(**json.loads(line))
                out[e.id] = e
    return out


def _append(e: Experiment, path: pathlib.Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(asdict(e), sort_keys=True) + "\n")


def new(hypothesis: str, benchmark: str, parent: str | None, path: pathlib.Path = DEFAULT_LOG) -> Experiment:
    e = Experiment(
        id=f"E{len(read(path)) + 1:03d}",
        hypothesis=hypothesis,
        benchmark=benchmark,
        parent=parent,
        status="open",
        opened=ledger.now(),
    )
    _append(e, path)
    return e


def close(id: str, outcome: str, notes: str | None, path: pathlib.Path = DEFAULT_LOG) -> Experiment:
    e = read(path).get(id)
    if e is None:
        raise KeyError(f"unknown experiment {id}")
    if e.status == "closed":
        raise ValueError(f"experiment {id} is already closed ({e.outcome})")
    e.status, e.outcome, e.notes, e.closed = "closed", outcome, notes, ledger.now()
    _append(e, path)
    return e


def add_parser(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    p = sub.add_parser("exp", help="experiment log: new, close, list")
    p.add_argument("--log", type=pathlib.Path, default=DEFAULT_LOG)
    s = p.add_subparsers(dest="exp_cmd", required=True)
    n = s.add_parser("new", help="open an experiment and print its id")
    n.add_argument("hypothesis")
    n.add_argument("--bench", required=True, choices=("invsqrt", "dqi", "dfthcsos"))
    n.add_argument("--parent", help="sha256 of the circuit this starts from")
    c = s.add_parser("close", help="record the outcome of an experiment")
    c.add_argument("id")
    c.add_argument("outcome", choices=OUTCOMES)
    c.add_argument("--notes")
    li = s.add_parser("list", help="list experiments with their linked verify runs")
    li.add_argument("--ledger", type=pathlib.Path, default=ledger.DEFAULT_LEDGER)


def run(a: argparse.Namespace) -> int:
    try:
        if a.exp_cmd == "new":
            print(new(a.hypothesis, a.bench, a.parent, a.log).id)
        elif a.exp_cmd == "close":
            e = close(a.id, a.outcome, a.notes, a.log)
            print(f"{e.id} closed: {e.outcome}")
        else:
            runs = [r for r in ledger.read(a.ledger) if r.experiment] if a.ledger.exists() else []
            for e in read(a.log).values():
                mine = [r for r in runs if r.experiment == e.id]
                print(
                    f"{e.id}\t{e.status}\t{e.outcome or '-'}\t{e.benchmark}\t{len(mine)} runs\t{e.hypothesis}"
                )
    except (KeyError, ValueError) as err:
        print(f"error: {err.args[0]}")
        return 2
    return 0
