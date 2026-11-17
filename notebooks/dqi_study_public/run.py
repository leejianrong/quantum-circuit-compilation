"""Kaggle kernel: aggregate structure scan of the public 70x DQI circuit next to our own `fixed4` (QCC-19).

Inputs (kernel-metadata.json): koushikrudra's notebook output (submission.zip holds dqi.kmb, read as data and never
executed) and the output of our `qcc-dqi-gen` kernel (holds fixed4.kmb). Each circuit goes through `dqi_gen.study`
(counts only: instruction mix, Toffolis per window, qubit-block lifetimes, tag names). Output: study_*.json.
"""

import pathlib
import resource
import shutil
import subprocess
import sys
import zipfile

INPUT = pathlib.Path("/kaggle/input")
OUT = pathlib.Path("/kaggle/working")
REPO = OUT / "repo"
COMP = next(p.parent for p in INPUT.glob("**/verifiers") if (p.parent / "kickmix").exists())
subprocess.run(
    ["git", "clone", "--depth=1", "https://github.com/leejianrong/quantum-circuit-compilation", str(REPO)],
    check=True,
)
cands: dict[str, pathlib.Path] = {}
for z in sorted(INPUT.glob("**/submission.zip")):
    dest = OUT / "cand" / z.parent.name
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(z) as f, f.open("dqi.kmb") as s, open(dest / "dqi.kmb", "wb") as d:
        shutil.copyfileobj(s, d, 1 << 24)
    cands[f"public_{z.parent.name}"] = dest / "dqi.kmb"
for p in sorted(INPUT.glob("**/fixed4.kmb")):
    cands["own_fixed4"] = p
env = {"PYTHONPATH": f"{REPO / 'src'}:{COMP / 'kickmix'}", "PATH": "/usr/bin:/bin:/usr/local/bin"}
for name, p in cands.items():
    print("study", name, p.stat().st_size / 1e6, "MB", flush=True)
    proc = subprocess.run(
        [sys.executable, "-m", "dqi_gen.study", str(p), "--out", str(OUT / f"study_{name}.json")],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
    )
    print(proc.stdout[-3000:], proc.stderr[-1500:], flush=True)
    peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024 / 1024
    print(f"peak child RSS {peak:.1f} GB", flush=True)
shutil.rmtree(OUT / "cand", ignore_errors=True)
shutil.rmtree(REPO, ignore_errors=True)
