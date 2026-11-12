"""`bench promote`: the gate between a verified candidate and `best/` (ADR-0001, ADR-0003).

A candidate is promoted only if the ledger shows, for exactly this circuit (sha256):
 * at least `min_salts` full-strength salts verified in total (reduced-shot, screen, leaderboard and
   public-reference rows never count),
 * no failure anywhere: every full-strength row is PASS with 0 failures,
 * a worst-salt cost strictly below the worst-salt cost of the circuit now in `best/`
   (if that circuit has no verified rows, it is replaced but the report says so).
Salts are counted as the sum over qualifying rows, since each row is a separate verification run.
Rerunning the same salts adds nothing real, so keep `--min-salts` honest. Each promotion is appended to
`ledger/promotions.jsonl`.
"""

import argparse
import json
import pathlib
import shutil
from dataclasses import dataclass, field

from bench import ledger, pack

DEFAULT_PROMOTIONS = pathlib.Path("ledger/promotions.jsonl")
NOT_EVIDENCE = {"screen", "leaderboard", "public-reference"}


@dataclass
class Decision:
    ok: bool
    reasons: list[str] = field(default_factory=list)
    salts: int = 0
    cost: float | None = None  # worst-salt cost of the candidate
    prev_cost: float | None = None  # worst-salt cost of the circuit in best/, if verified
    notes: list[str] = field(default_factory=list)


def evidence(rows: list[ledger.Row], bench: str, sha: str) -> list[ledger.Row]:
    """Full-strength rows for this circuit that count as verification evidence."""
    return [
        r
        for r in rows
        if r.bench == bench and r.circuit_sha256 == sha and not r.reduced_shots and r.kind not in NOT_EVIDENCE
    ]


def decide(
    rows: list[ledger.Row], bench: str, candidate_sha: str, current_sha: str | None, min_salts: int
) -> Decision:
    ev = evidence(rows, bench, candidate_sha)
    d = Decision(ok=True, salts=sum(r.salts for r in ev))
    if not ev:
        d.reasons.append("no full-strength verification rows in the ledger for this circuit")
        d.ok = False
        return d
    bad = [r for r in ev if r.status != "PASS" or r.failures]
    if bad:
        d.reasons.append(f"{len(bad)} verification row(s) failed: any failure blocks promotion")
    costs = [r.cost for r in ev if r.cost is not None]
    d.cost = max(costs) if costs else None
    if d.cost is None:
        d.reasons.append("no scored cost recorded")
    if d.salts < min_salts:
        d.reasons.append(f"only {d.salts} full-strength salts verified, need {min_salts}")
    if current_sha and current_sha != candidate_sha:
        prev = [
            r.cost for r in evidence(rows, bench, current_sha) if r.cost is not None and r.status == "PASS"
        ]
        if prev:
            d.prev_cost = max(prev)
            if d.cost is not None and d.cost >= d.prev_cost:
                d.reasons.append(f"cost {d.cost:.6g} is not below the current best {d.prev_cost:.6g}")
        else:
            d.notes.append("the circuit now in best/ has no verified ledger rows; replacing it")
    elif current_sha == candidate_sha:
        d.reasons.append("this circuit is already in best/")
    d.ok = not d.reasons
    return d


def _current(best: pathlib.Path, bench: str) -> pathlib.Path | None:
    d = best / bench
    if not d.is_dir():
        return None
    return d if bench == "dfthcsos" else next((p for p in d.glob(f"{bench}.km[xb]")), None)


def _install(best: pathlib.Path, bench: str, candidate: pathlib.Path) -> None:
    """Replace best/<bench> with the candidate, restoring the old store if it would not pack."""
    target = best / bench
    backup = best / f".{bench}.prev"
    if backup.exists():
        shutil.rmtree(backup)
    if target.exists():
        target.rename(backup)
    try:
        target.mkdir(parents=True)
        if bench == "dfthcsos":
            for f in sorted(candidate.iterdir()):
                shutil.copy2(f, target / f.name)
        else:
            shutil.copy2(candidate, target / f"{bench}{candidate.suffix}")
        if all((best / b).is_dir() for b in pack.BENCHES):
            pack.collect(best)  # the same file checks the archive will apply
    except Exception:
        shutil.rmtree(target, ignore_errors=True)
        if backup.exists():
            backup.rename(target)
        raise
    shutil.rmtree(backup, ignore_errors=True)


def run(
    bench: str,
    candidate: pathlib.Path,
    ledger_path: pathlib.Path,
    best: pathlib.Path,
    min_salts: int,
    dry_run: bool,
    promotions: pathlib.Path = DEFAULT_PROMOTIONS,
) -> int:
    if not candidate.exists():
        print(f"BLOCKED: {candidate} does not exist")
        return 1
    rows = ledger.read(ledger_path) if ledger_path.exists() else []
    cand_sha = ledger.sha256_path(candidate)
    cur = _current(best, bench)
    cur_sha = ledger.sha256_path(cur) if cur else None
    d = decide(rows, bench, cand_sha, cur_sha, min_salts)
    for n in d.notes:
        print("note:", n)
    if not d.ok:
        print(f"BLOCKED {bench} {cand_sha[:12]}:")
        for r in d.reasons:
            print("  -", r)
        return 1
    print(
        f"OK {bench} {cand_sha[:12]}: {d.salts} salts, worst cost {d.cost:.6g}"
        + (f" (best was {d.prev_cost:.6g})" if d.prev_cost else "")
    )
    if dry_run:
        print("dry run: best/ unchanged")
        return 0
    try:
        _install(best, bench, candidate)
    except (pack.PackError, OSError) as err:
        print(f"BLOCKED: installing into best/ failed and was rolled back: {err}")
        return 1
    promotions.parent.mkdir(parents=True, exist_ok=True)
    with promotions.open("a") as f:
        f.write(
            json.dumps(
                {
                    "ts": ledger.now(),
                    "bench": bench,
                    "sha256": cand_sha,
                    "prev_sha256": cur_sha,
                    "cost": d.cost,
                    "prev_cost": d.prev_cost,
                    "salts": d.salts,
                    "git_sha": ledger.git_sha(),
                },
                sort_keys=True,
            )
            + "\n"
        )
    print(f"promoted into {best / bench}")
    return 0


def add_parser(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    p = sub.add_parser("promote", help="copy a verified candidate into best/ if the ledger allows (ADR-0001)")
    p.add_argument("bench", choices=pack.BENCHES)
    p.add_argument("candidate", type=pathlib.Path, help="circuit file (dfthcsos: the submission directory)")
    p.add_argument("--ledger", type=pathlib.Path, default=ledger.DEFAULT_LEDGER)
    p.add_argument("--best", type=pathlib.Path, default=pathlib.Path("best"))
    p.add_argument("--min-salts", type=int, default=10, help="full-strength salts required (ADR-0001: 10)")
    p.add_argument("--dry-run", action="store_true", help="check the gate, change nothing")
