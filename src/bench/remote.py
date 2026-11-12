"""`bench kaggle`: run a Kaggle kernel to completion and bring its ledger rows back (ADR-0002).

    bench kaggle run notebooks/dqi_verify      push, wait, download output, merge ledger rows
    bench kaggle fetch leejianrong/qcc-dqi-gen  download the output of a kernel that already ran

Kernels write a ledger (`/kaggle/working/ledger/results.jsonl`, the same rows `bench verify` writes).
Merging skips rows already present, so fetching twice is harmless. Kaggle credentials come from the
Kaggle CLI's own configuration; nothing here reads or prints them.
"""

import argparse
import json
import pathlib
import re
import subprocess
import sys
import time
from collections.abc import Callable, Sequence

Runner = Callable[[list[str]], subprocess.CompletedProcess[str]]
TERMINAL = ("COMPLETE", "ERROR", "CANCEL")


def kaggle(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["kaggle", *args], capture_output=True, text=True, check=False)


def slug_of(kernel_dir: pathlib.Path) -> str:
    """The kernel id from kernel-metadata.json (owner/slug). Kaggle may derive the slug from the title."""
    return str(json.loads((kernel_dir / "kernel-metadata.json").read_text())["id"])


def parse_status(text: str) -> str | None:
    m = re.search(r"KernelWorkerStatus\.(\w+)", text)
    return m.group(1) if m else None


def wait(
    slug: str,
    run: Runner = kaggle,
    poll: float = 60.0,
    timeout: float = 4 * 3600,
    sleep: Callable[[float], None] = time.sleep,
    log: Callable[[str], None] = print,
) -> str:
    """Poll until the kernel reaches a terminal state; raise TimeoutError otherwise."""
    waited = 0.0
    while True:
        status = parse_status(run(["kernels", "status", slug]).stdout)
        log(f"{slug}: {status or 'unknown'}")
        if status and status.startswith(TERMINAL):
            return status
        if waited >= timeout:
            raise TimeoutError(f"{slug} still {status} after {timeout:.0f}s")
        sleep(poll)
        waited += poll


def fetch(slug: str, out_dir: pathlib.Path, run: Runner = kaggle) -> pathlib.Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    proc = run(["kernels", "output", slug, "-p", str(out_dir)])
    if proc.returncode != 0:
        raise RuntimeError(f"kaggle kernels output failed: {proc.stderr.strip() or proc.stdout.strip()}")
    return out_dir


def merge_ledger(remote: pathlib.Path, local: pathlib.Path) -> int:
    """Append remote ledger lines not already in the local ledger. Returns how many were added."""
    if not remote.exists():
        return 0
    have = set(local.read_text().splitlines()) if local.exists() else set()
    new = [ln for ln in remote.read_text().splitlines() if ln and ln not in have]
    for ln in new:
        json.loads(ln)  # refuse to append anything that is not a JSON row
    if new:
        local.parent.mkdir(parents=True, exist_ok=True)
        with local.open("a") as f:
            f.writelines(ln + "\n" for ln in new)
    return len(new)


def run_kernel(
    kernel_dir: pathlib.Path,
    ledger_path: pathlib.Path,
    out_root: pathlib.Path,
    run: Runner = kaggle,
    poll: float = 60.0,
    timeout: float = 4 * 3600,
) -> int:
    slug = slug_of(kernel_dir)
    pushed = run(["kernels", "push", "-p", str(kernel_dir)])
    print(pushed.stdout.strip().splitlines()[-1] if pushed.stdout.strip() else pushed.stderr.strip())
    if pushed.returncode != 0:
        return 1
    return fetch_kernel(slug, ledger_path, out_root, run, poll, timeout)


def fetch_kernel(
    slug: str,
    ledger_path: pathlib.Path,
    out_root: pathlib.Path,
    run: Runner = kaggle,
    poll: float = 0.0,
    timeout: float = 0.0,
) -> int:
    try:
        status = wait(slug, run, poll, timeout)
    except TimeoutError as err:
        print(f"TIMEOUT: {err}. Fetch later with: bench kaggle fetch {slug}")
        return 1
    out = fetch(slug, out_root / slug.replace("/", "__"), run)
    added = merge_ledger(out / "ledger" / "results.jsonl", ledger_path)
    print(f"{slug}: {status}; output in {out}; {added} new ledger row(s) merged into {ledger_path}")
    return 0 if status == "COMPLETE" else 1


def add_parser(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    p = sub.add_parser("kaggle", help="run or fetch a Kaggle kernel and merge its ledger rows")
    k = p.add_subparsers(dest="kaggle_cmd", required=True)
    for name, helptext in (
        ("run", "push a kernel directory, wait, fetch, merge"),
        ("fetch", "fetch a finished kernel"),
    ):
        q = k.add_parser(name, help=helptext)
        q.add_argument("target", help="kernel directory (run) or owner/slug (fetch)")
        q.add_argument("--ledger", type=pathlib.Path, default=pathlib.Path("ledger/results.jsonl"))
        q.add_argument("--out", type=pathlib.Path, default=pathlib.Path("out/kaggle"))
        q.add_argument("--poll", type=float, default=60.0, help="seconds between status checks")
        q.add_argument(
            "--timeout", type=float, default=4 * 3600, help="give up waiting after this many seconds"
        )


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m bench.remote")
    sub = p.add_subparsers(dest="cmd", required=True)
    add_parser(sub)
    a = p.parse_args(argv)
    return dispatch(a)


def dispatch(a: argparse.Namespace) -> int:
    if a.kaggle_cmd == "run":
        return run_kernel(pathlib.Path(a.target), a.ledger, a.out, kaggle, a.poll, a.timeout)
    return fetch_kernel(a.target, a.ledger, a.out, kaggle, a.poll, a.timeout)


if __name__ == "__main__":
    sys.exit(main())
