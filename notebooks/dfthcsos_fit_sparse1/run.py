"""Kaggle kernel: our own dfthcsos fits on free CPU (QCC-16; ADR-0009, no pod). Edit JOBS and push.

Clones BRANCH of the public repo, builds ``tsym.npy`` from the competition FCIDUMP (never committed),
then runs
each job (a ``python`` argument list) with output streamed to /kaggle/working/<name>.log. Fits checkpoint into
/kaggle/working/fit/<run> and resume from there; if a previous kernel is attached through
``kernel_sources`` its
``fit/`` directory is copied first, so a chain of sessions continues one run. Push with
``kaggle kernels push -p notebooks/dfthcsos_fit``; ``bench kaggle fetch leejianrong/qcc-dfthcsos-fit`` brings
the output back.
"""

import os
import pathlib
import shutil
import subprocess
import time

BRANCH = "main"
OUT = pathlib.Path("/kaggle/working")
FIT = OUT / "fit"
# Each job: (name, argv after `python`, max seconds). {fit}, {repo}, {comp} expand to paths.
JOBS = [
    (
        "sparse",
        [
            "scripts/run_fit.py",
            "--tsym",
            "{fit}/tsym.npy",
            "--shape",
            "8",
            "143",
            "44",
            "--init",
            "sparse",
            "--seed",
            "1",
            "--iters",
            "100000",
            "--threads",
            "4",
            "--out",
            "{fit}/sparse_s1",
            "--checkpoint-every",
            "100",
            "--max-secs",
            "39000",
        ],
        40000,
    ),
]

INPUT = pathlib.Path("/kaggle/input")
COMP = next(p.parent for p in INPUT.glob("**/verifiers") if (p.parent / "kickmix").exists())
REPO = OUT / "repo"
URL = "https://github.com/leejianrong/quantum-circuit-compilation"
subprocess.run(["git", "clone", "--depth=1", "--branch", BRANCH, URL, str(REPO)], check=True)
FIT.mkdir(parents=True, exist_ok=True)
for pattern in ("*/fit", "*/*/fit", "*/*/*/fit"):  # a previous kernel's output, attached as a kernel source
    for prev in INPUT.glob(pattern):
        shutil.copytree(prev, FIT, dirs_exist_ok=True)
env = {**os.environ, "PYTHONPATH": str(REPO / "src"), "QCC_DATA": str(COMP)}
if not (FIT / "tsym.npy").exists():
    # the host verifier imports kickmix at module level (the pip wheel, as in uv sync)
    subprocess.run(["pip", "install", "-q", "kickmix"], check=True)
    subprocess.run(["python", "scripts/dfthcsos_fit.py", str(FIT)], cwd=REPO, env=env, check=True)
for name, argv, limit in JOBS:
    argv = [a.format(fit=FIT, repo=REPO, comp=COMP) for a in argv]
    print(f"== {name}: python {' '.join(argv)}", flush=True)
    start = time.monotonic()
    with open(OUT / f"{name}.log", "a") as log:
        proc = subprocess.Popen(["python", *argv], cwd=REPO, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            proc.wait(timeout=limit)
        except subprocess.TimeoutExpired:
            proc.terminate()
            proc.wait()
    with open(OUT / "jobs.txt", "a") as f:
        f.write(f"{name}\texit={proc.returncode}\twall_s={time.monotonic() - start:.0f}\n")
# keep only what the next session needs (tsym is rebuilt from the FCIDUMP in a minute)
(FIT / "tsym.npy").unlink(missing_ok=True)
