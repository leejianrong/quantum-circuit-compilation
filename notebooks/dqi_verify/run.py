"""Kaggle kernel: verify DQI circuits with the official verifier, recording peak RSS and wall time.

Inputs (attached in kernel-metadata.json): the competition data and a public dataset holding the
candidate circuits. Output: /kaggle/working/ledger/results.jsonl and timing.txt.
Run as: python run.py <salts> (default 2).
"""

import pathlib
import resource
import subprocess
import sys

INPUT = pathlib.Path("/kaggle/input")
for d in sorted(INPUT.glob("*")) + sorted(INPUT.glob("*/*")):
    print("input:", d, flush=True)
COMP = next(p.parent for p in INPUT.glob("**/verifiers") if (p.parent / "kickmix").exists())
print("competition data dir:", COMP, flush=True)
REPO = pathlib.Path("/kaggle/working/repo")
OUT = pathlib.Path("/kaggle/working")
salts = sys.argv[1] if len(sys.argv) > 1 else "10"

subprocess.run(
    ["git", "clone", "--depth=1", "https://github.com/leejianrong/quantum-circuit-compilation", str(REPO)],
    check=True,
)
candidates = {}  # baseline already measured (472 s, 9.1 GB, 2 salts)
for p in INPUT.glob("**/dqi.kmb"):
    if "sample_submission" not in p.parts:
        candidates[f"public:{p.parent.parent.name}/{p.parent.name}"] = p

for name, path in candidates.items():
    print(f"== {name}: {path} ({path.stat().st_size / 1e6:.0f} MB)", flush=True)
    before = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from bench.cli import main; sys.exit(main(sys.argv[1:]))",
            "verify",
            "dqi",
            str(path),
            "--salts",
            salts,
            "--data",
            str(COMP),
            "--ledger",
            str(OUT / "ledger" / "results.jsonl"),
        ],
        cwd=REPO,
        env={"PYTHONPATH": str(REPO / "src"), "PATH": "/usr/bin:/bin:/usr/local/bin"},
    )
    peak_mb = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024
    with open(OUT / "timing.txt", "a") as f:
        f.write(f"{name}\t{path}\texit={proc.returncode}\tmax_child_rss_mb={peak_mb:.0f}\n")
    print(f"peak child RSS so far: {peak_mb:.0f} MB (before: {before / 1024:.0f})", flush=True)
