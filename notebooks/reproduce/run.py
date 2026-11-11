"""Rebuild and verify our submission from public circuits (QCC-9).

What this does, in order:
 1. Finds the public circuits in the attached dataset and checks each file's sha256 against the
    published hashes (so you know exactly which files are used).
 2. Packs them into submission.zip with our `bench pack`, which mirrors the metric's file checks.
 3. Verifies each benchmark with the OFFICIAL verifiers (salts are ours, not the secret ones) and
    prints the cost, the ratio against the baseline cost and the geometric-mean score.

Credit: the circuits are other participants' public work (see CREDITS below); this notebook only
verifies, packages and measures them. Our code is Apache-2.0. Each circuit keeps its authors' terms.
Run as: python run.py [dqi_salts] [invsqrt_salts] [dfthcsos_salts]   (defaults 1 1 3)
"""

import hashlib
import json
import pathlib
import shutil
import subprocess
import sys

INPUT = pathlib.Path("/kaggle/input")
WORK = pathlib.Path("/kaggle/working")
REPO = WORK / "repo"
dqi_salts, inv_salts, dft_salts = (sys.argv[1:4] + ["1", "1", "3"][len(sys.argv[1:4]) :])[:3]

EXPECTED = {  # sha256 of the plain files, from docs/PROVENANCE.md
    "invsqrt.kmb": "c6519219f598c1b621c00e51d5c5d8b74e450a68586f56c58e569f1ca4f84536",
    "dqi.kmb": "e9f54be304cbdcda7306729c335b1a2314a45d0ca818e05cf60e45ddee969bc4",
    "dfthcsos/submission.npz": "91d0ad2554e0c039ad8268b810812dab03110ca671bbdb65976dc6f82abd909b",
}
BASELINE = {  # reference costs from the release manifests
    "invsqrt": 2_076_774.23,
    "dqi": 24_439_463_583_672.9,
    "dfthcsos": 3_355_599_588.32,
}
CREDITS = """CREDITS (circuits are public work of other participants; terms are theirs):
  invsqrt c6519219  maoxin123 (CSWAP-reduced variant of the 13b5bf7a line: ozertuu, kirilltym,
                    Atakan Aldemir, Hosen42, syed3000, mrmeows, busyaprime, yoyobar)
  dqi e9f54be3      Atakan Aldemir (phase folds) on ozertuu (readout rewrite); decoder design from
                    jday96314's QuantumAI repository, which states no licence
  dfthcsos 91d0ad25 maoxin123 (weight refit) on syed3000 loaders
Source dataset: pramitdas/qcc-public-frontier-submission. See docs/PROVENANCE.md in our repo."""


def sha256(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run(*cmd: str) -> subprocess.CompletedProcess[str]:
    print("$", " ".join(cmd), flush=True)
    return subprocess.run(
        cmd,
        cwd=REPO,
        text=True,
        env={"PYTHONPATH": str(REPO / "src"), "PATH": "/usr/bin:/bin:/usr/local/bin"},
    )


print(CREDITS, flush=True)
data = next(p.parent for p in INPUT.glob("**/verifiers") if (p.parent / "kickmix").exists())
sub = next(
    p.parent
    for p in INPUT.glob("**/invsqrt.kmb")
    if "sample_submission" not in p.parts and data not in p.parents
)
print("competition data:", data, "\ncandidate circuits:", sub, flush=True)

subprocess.run(
    ["git", "clone", "--depth=1", "https://github.com/leejianrong/quantum-circuit-compilation", str(REPO)],
    check=True,
)
for rel, want in EXPECTED.items():
    got = sha256(sub / rel)
    print(f"{'OK ' if got == want else 'BAD'} {rel} {got[:12]}", flush=True)
    assert got == want, f"{rel}: hash differs from the published one"

best = REPO / "best"
for name in ("invsqrt", "dqi", "dfthcsos"):
    (best / name).mkdir(parents=True, exist_ok=True)
shutil.copy(sub / "invsqrt.kmb", best / "invsqrt")
shutil.copy(sub / "dqi.kmb", best / "dqi")
for f in (sub / "dfthcsos").iterdir():
    shutil.copy(f, best / "dfthcsos")
run(
    sys.executable,
    "-c",
    "import sys; from bench.cli import main; sys.exit(main(sys.argv[1:]))",
    "pack",
    "--out",
    str(WORK / "submission.zip"),
)

ledger = WORK / "ledger" / "results.jsonl"
cli = "import sys; from bench.cli import main; sys.exit(main(sys.argv[1:]))"
for bench, circuit, salts in (
    ("dfthcsos", best / "dfthcsos", dft_salts),
    ("dqi", best / "dqi" / "dqi.kmb", dqi_salts),
    ("invsqrt", best / "invsqrt" / "invsqrt.kmb", inv_salts),
):
    run(
        sys.executable,
        "-c",
        cli,
        "verify",
        bench,
        str(circuit),
        "--salts",
        salts,
        "--data",
        str(data),
        "--ledger",
        str(ledger),
    )

rows = [json.loads(line) for line in ledger.read_text().splitlines()]
print("\n=== RESULT ===")
ratios = []
for r in rows:
    ratio = BASELINE[r["bench"]] / r["cost"] if r["cost"] else 0.0
    ratios.append(ratio)
    print(
        f"{r['bench']:9s} {r['status']} salts={r['salts']} failures={r['failures']} "
        f"cost={r['cost']:.6g} ratio={ratio:.3f}"
    )
if len(ratios) == 3 and all(ratios):
    print(f"geometric-mean score = {(ratios[0] * ratios[1] * ratios[2]) ** (1 / 3):.3f}")
