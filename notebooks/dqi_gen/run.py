"""Kaggle kernel: run our DQI generator jobs at full size (ADR-0002). One script, edit JOBS and push.

Clones BRANCH of the public repo, then runs each job (a `python -m ...` argument list) with PYTHONPATH=src
and QCC_DATA pointing at the competition data. Wall time and peak child RSS go to /kaggle/working/jobs.txt;
job outputs (JSON, ledger rows) go to /kaggle/working. Push with `kaggle kernels push -p notebooks/dqi_gen`.
"""

import pathlib
import resource
import subprocess
import time

BRANCH = "main"
OUT = pathlib.Path("/kaggle/working")
# Each job: (name, argv after `python`). {out} expands to /kaggle/working, {repo} to the clone.
JOBS = [
    (
        "build-lanczos-full",
        [
            "-m",
            "dqi_gen.instances",
            "--gen",
            "lanczos",
            "--instance",
            "full",
            "--salts",
            "0",
            "--sha",
            "--save",
            "{out}/lanczos.kmb",
        ],
    ),
    (
        "verify-lanczos-full",
        [
            "-c",
            "import sys; from bench.cli import main; sys.exit(main(sys.argv[1:]))",
            "verify",
            "dqi",
            "{out}/lanczos.kmb",
            "--salts",
            "5",
            "--data",
            "{comp}",
            "--ledger",
            "{out}/ledger/results.jsonl",
        ],
    ),
]

INPUT = pathlib.Path("/kaggle/input")
COMP = next(p.parent for p in INPUT.glob("**/verifiers") if (p.parent / "kickmix").exists())
REPO = OUT / "repo"
subprocess.run(
    [
        "git",
        "clone",
        "--depth=1",
        "--branch",
        BRANCH,
        "https://github.com/leejianrong/quantum-circuit-compilation",
        str(REPO),
    ],
    check=True,
)
env = {"PYTHONPATH": str(REPO / "src"), "QCC_DATA": str(COMP), "PATH": "/usr/bin:/bin:/usr/local/bin"}
for name, argv in JOBS:
    argv = [a.format(out=OUT, repo=REPO, comp=COMP) for a in argv]
    print(f"== {name}: python {' '.join(argv)}", flush=True)
    start = time.monotonic()
    proc = subprocess.run(["python", *argv], cwd=REPO, env=env, capture_output=True, text=True)
    print(proc.stdout, proc.stderr[-2000:], flush=True)
    (OUT / f"{name}.out").write_text(proc.stdout)
    peak_gb = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024 / 1024
    wall = time.monotonic() - start
    line = f"{name}\texit={proc.returncode}\twall_s={wall:.0f}\tpeak_child_rss_gb={peak_gb:.1f}\n"
    print(line, flush=True)
    with open(OUT / "jobs.txt", "a") as f:
        f.write(line)
