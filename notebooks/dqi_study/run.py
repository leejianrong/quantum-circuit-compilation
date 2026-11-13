"""Kaggle kernel: aggregate structure scan of the public DQI circuit (ADR-0009 stage 2, QCC-19).

Streams the text dump of the circuit in the attached public dataset through `dqi_gen.study` (counts only:
instruction mix, Toffolis per window, qubit-block lifetimes, tag names). Output: /kaggle/working/study_*.json.
The circuit is never written to the output.
"""

import pathlib
import resource
import subprocess
import sys

INPUT = pathlib.Path("/kaggle/input")
OUT = pathlib.Path("/kaggle/working")
REPO = OUT / "repo"
COMP = next(p.parent for p in INPUT.glob("**/verifiers") if (p.parent / "kickmix").exists())
subprocess.run(
    ["git", "clone", "--depth=1", "https://github.com/leejianrong/quantum-circuit-compilation", str(REPO)],
    check=True,
)
env = {"PYTHONPATH": f"{REPO / 'src'}:{COMP / 'kickmix'}", "PATH": "/usr/bin:/bin:/usr/local/bin"}
for p in INPUT.glob("**/dqi.kmb"):
    if "sample_submission" in p.parts:
        continue
    name = f"{p.parent.parent.name}_{p.parent.name}"
    print("study", name, p.stat().st_size / 1e6, "MB", flush=True)
    proc = subprocess.run(
        [sys.executable, "-m", "dqi_gen.study", str(p), "--out", str(OUT / f"study_{name}.json")],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
    )
    print(proc.stdout, proc.stderr[-1500:], flush=True)
    peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024 / 1024
    print(f"peak child RSS {peak:.1f} GB", flush=True)
