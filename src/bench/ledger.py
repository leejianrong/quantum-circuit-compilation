"""Append-only JSONL ledger of verification runs (ADR-0001)."""

import hashlib
import json
import pathlib
import socket
import subprocess
from dataclasses import asdict, dataclass

SCHEMA = 1
DEFAULT_LEDGER = pathlib.Path("ledger/results.jsonl")


@dataclass
class Row:
    bench: str
    circuit: str
    circuit_sha256: str
    status: str  # "PASS" or "FAIL"
    cost: float | None  # worst (largest) official cost over the salts; None if nothing scored
    costs: list[float]
    shots_divisor: int
    reduced_shots: bool  # inner-loop only; never gates promotion
    salts: int
    failures: int
    error: str | None
    wall_s: float
    git_sha: str
    host: str = ""
    schema: int = SCHEMA

    def __post_init__(self) -> None:
        self.host = self.host or socket.gethostname()


def sha256_path(path: pathlib.Path) -> str:
    """Hash a file, or a directory (sorted relative names plus file hashes)."""
    if path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    h = hashlib.sha256()
    for f in sorted(p for p in path.rglob("*") if p.is_file()):
        h.update(f.relative_to(path).as_posix().encode() + b"\0" + sha256_path(f).encode() + b"\n")
    return h.hexdigest()


def git_sha() -> str:
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        )
        dirty = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return sha.stdout.strip() + ("-dirty" if dirty.stdout.strip() else "")


def append(row: Row, path: pathlib.Path = DEFAULT_LEDGER) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(asdict(row), sort_keys=True) + "\n")


def read(path: pathlib.Path = DEFAULT_LEDGER) -> list[Row]:
    return [Row(**json.loads(line)) for line in path.read_text().splitlines() if line]
