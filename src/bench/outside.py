"""Outside-world rows for the ledger: public-reference costs and leaderboard scores (docs/MEASUREMENT.md).

Both are appended idempotently and never touch existing lines. Neither is verified by us.
"""

import argparse
import csv
import io
import pathlib
import subprocess
from collections.abc import Callable

from bench import ledger

COMPETITION = "google-verifiable-quantum-circuit-compilation"
# (bench, sha256, reported cost). Costs are as reported in docs/PROVENANCE.md; a test keeps the
# hashes in sync with that file. dfthcsos hashes are of submission.npz.
PUBLIC = [
    ("invsqrt", "c6519219f598c1b621c00e51d5c5d8b74e450a68586f56c58e569f1ca4f84536", 94599.61),
    ("invsqrt", "034c7c2a54d51e13aff6e62ec4c14997d3968b6c11122146c57290b1a1b8c7e2", 95345.54),
    ("invsqrt", "46743f7f8f9b85c76124fcd4062a6250706442971f56587e62cd797de000bfdd", 95345.55),
    ("dqi", "e9f54be304cbdcda7306729c335b1a2314a45d0ca818e05cf60e45ddee969bc4", 374686873087.0),
    ("dqi", "4432ec5fd63d7d70aab92d32f719d47539d0ff66ae0cb0b964c914e01fece431", 374735446629.0),
    ("dfthcsos", "91d0ad2554e0c039ad8268b810812dab03110ca671bbdb65976dc6f82abd909b", 299614422.44),
    ("dfthcsos", "ad1a4d28e66585e4b94a3b3111c4f64aff81f25f52611fce5c690bbce0e5e6ec", 299654754.95),
    ("dfthcsos", "8faa7e0bc40ea80793162639af856b0272bc8680eb2e36cca65a69bb3531fe9f", 299654755.24),
    ("dfthcsos", "3f72cbe5054043741683a3c487f9cdffb7cb62770b0399a2f96184d2449a0595", 299654755.41),
]
LB_STATUS = {"COMPLETE": "PASS", "ERROR": "FAIL", "PENDING": "PENDING"}


def _row(bench: str, circuit: str, sha: str, status: str, cost: float | None, kind: str) -> ledger.Row:
    return ledger.Row(
        bench=bench,
        circuit=circuit,
        circuit_sha256=sha,
        status=status,
        cost=cost,
        costs=[],
        shots_divisor=1,
        reduced_shots=False,
        salts=0,
        failures=0,
        error=None,
        wall_s=0.0,
        git_sha=ledger.git_sha(),
        ts=ledger.now(),
        kind=kind,
    )


def _existing(path: pathlib.Path, kind: str) -> list[ledger.Row]:
    return [r for r in ledger.read(path) if r.kind == kind] if path.exists() else []


def backfill(path: pathlib.Path = ledger.DEFAULT_LEDGER) -> int:
    """Append kind=public-reference rows (status UNVERIFIED) that are not in the ledger yet."""
    have = {(r.bench, r.circuit_sha256) for r in _existing(path, "public-reference")}
    added = 0
    for bench, sha, cost in PUBLIC:
        if (bench, sha) not in have:
            circuit = f"public:{bench}/{sha[:8]}"
            ledger.append(_row(bench, circuit, sha, "UNVERIFIED", cost, "public-reference"), path)
            added += 1
    return added


def parse_submissions(text: str) -> list[dict[str, str]]:
    """Parse `kaggle competitions submissions -v` CSV, skipping any warning lines before the header."""
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines) if ln.startswith("ref,")), len(lines))
    return list(csv.DictReader(io.StringIO("\n".join(lines[start:]))))


def fetch_submissions() -> str:
    # No credentials are read or printed here; the Kaggle CLI finds its own.
    return subprocess.run(
        ["kaggle", "competitions", "submissions", COMPETITION, "-v"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def lb(path: pathlib.Path = ledger.DEFAULT_LEDGER, fetch: Callable[[], str] | None = None) -> int:
    """Append a kind=leaderboard row per (submission ref, status) not seen yet. Returns rows added.

    PENDING becomes PENDING, COMPLETE becomes PASS (with the public score), ERROR becomes FAIL. A
    pending submission gets a second row once it completes; the earlier row stays.
    """
    have = {(r.circuit, r.status) for r in _existing(path, "leaderboard")}
    added = 0
    for s in parse_submissions((fetch or fetch_submissions)()):
        state = s["status"].rsplit(".", 1)[-1].upper()
        status = LB_STATUS.get(state, state)
        circuit = f"submission:{s['ref']}"
        if (circuit, status) in have:
            continue
        row = _row("all", circuit, "", status, None, "leaderboard")
        row.ts = s["date"].replace(" ", "T").split(".")[0] + "+00:00"  # submission time (UTC)
        row.error = s["description"][:200] if status == "FAIL" else None
        if status == "PASS" and s.get("publicScore"):
            row.leaderboard_score = float(s["publicScore"])
        ledger.append(row, path)
        added += 1
    return added


def add_parsers(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    b = sub.add_parser("backfill", help="append public-reference rows (unverified) from PROVENANCE costs")
    b.add_argument("--ledger", type=pathlib.Path, default=ledger.DEFAULT_LEDGER)
    h = sub.add_parser("lb", help="pull our Kaggle submissions into kind=leaderboard rows")
    h.add_argument("--ledger", type=pathlib.Path, default=ledger.DEFAULT_LEDGER)


def run(a: argparse.Namespace) -> int:
    if a.cmd == "backfill":
        print(f"added {backfill(a.ledger)} public-reference rows")
        return 0
    try:
        print(f"added {lb(a.ledger)} leaderboard rows")
    except (OSError, subprocess.CalledProcessError) as err:
        print(f"error: kaggle submissions failed ({type(err).__name__})")
        return 1
    return 0
