"""Our wiring of the vendored v12 invsqrt builder: assemble its tree, build every prefix of the patches.

Runs inside the sandbox of ``scripts/invsqrt_port_stages.sh`` (CPython 3.13 with numpy and the
competition ``kickmix.so``, which this host cannot load). Standard library only.
``third_party/syed_invsqrt/src`` holds the 78 files the reference build executes; the rest of the
work tree (pinned data, certificates) comes from the downloaded archive, an input (QCC-68).

    stages.py assemble --archive A/src --vendored V/src --official DATA --work W
    stages.py prefix --tree T --upto K --out F.json
    stages.py ledger --archive A/src --vendored V/src --official DATA --work W --out L.json

A patch rebinds attributes of live modules, so every prefix runs in its own process. Prefix 0 is the unpatched
base (``candidate10``); prefix K applies the first K ``patch`` lines of ``patches/PATCH_ORDER.txt``.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

TOKEN = "@FG_ROOT@"


def assemble(archive: Path, vendored: Path, official: Path, work: Path) -> Path:
    """Copy the archive tree, check the vendored files equal it, relocate the token, add the host files."""
    tree = work / "tree"
    if tree.exists():
        shutil.rmtree(tree)
    shutil.copytree(archive, tree)
    for f in sorted(p for p in vendored.rglob("*") if p.is_file()):
        rel = f.relative_to(vendored)
        if (tree / rel).read_bytes() != f.read_bytes():
            raise SystemExit(f"vendored file differs from the archive: {rel}")
    base = tree / "work" / "c10"
    for d, subdirs, files in os.walk(tree):
        if Path(d) == base:
            subdirs[:] = []
            continue
        for name in files:
            if name.endswith((".py", ".sh")):
                p = Path(d) / name
                b = p.read_bytes()
                if TOKEN.encode() in b:
                    p.write_bytes(b.replace(TOKEN.encode(), str(tree).encode()))
    off = base / "narrow" / "base" / "official"
    (off / "kickmix").mkdir(parents=True, exist_ok=True)
    (off / "verifier_invsqrt").mkdir(parents=True, exist_ok=True)
    shutil.copy(official / "kickmix" / "kickmix.so", off / "kickmix" / "kickmix.so")
    for name in ("__init__.py", "nr_reference_circuit.py", "verify_submission_invsqrt.py"):
        src = official / "verifiers" / "invsqrt" / name
        if src.exists():
            shutil.copy(src, off / "verifier_invsqrt" / name)
    return tree


def patch_order(tree: Path) -> tuple[int, list[str]]:
    q = 0
    patches: list[str] = []
    for line in (tree / "patches" / "PATCH_ORDER.txt").read_text().splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0] == "Q":
            q = int(parts[1])
        elif len(parts) == 2 and parts[0] == "patch":
            patches.append(parts[1])
    return q, patches


def build_prefix(tree: Path, upto: int, width: int | None) -> dict[str, object]:
    """One build with the first ``upto`` patches: exact expectation and cost model of the emitted circuit."""
    os.environ["FG"] = str(tree)
    os.environ["NARROW"] = str(tree / "work" / "c10" / "narrow")
    os.chdir(tree)
    sys.path.insert(0, str(tree / "tools"))
    bv = importlib.import_module("build_variant")  # vendored, found on the path above

    _, patches = patch_order(tree)
    t0 = time.monotonic()
    mods = [bv.load_patch(str(tree / "patches" / n)) for n in patches[:upto]]
    patchset = bv.PatchSet(mods) if mods else None
    _ctx, circuit, text, _cuts, _trace, _layout = bv.build(patchset, width)
    program_cls = importlib.import_module("branch_prover").Program
    exact_expectation = importlib.import_module("fourier_resource_expectation").exact_expectation
    resources = exact_expectation(text)
    model = bv.cost_model(resources, circuit.num_qubits)
    return {
        "upto": upto,
        "width_limit": width,
        "patch": patches[upto - 1] if upto else "(base candidate10)",
        "qubits": circuit.num_qubits,
        "toffoli_like": model["toffoli_like"],
        "T": model["T"],
        "generic_rotations": model["generic_rotations"],
        "per_shot": model["per_shot"],
        "modelled_cost": model["modelled_cost"],
        "hmr_variables": program_cls(text).measurements,
        "seconds": round(time.monotonic() - t0, 1),
    }


def ledger(args: argparse.Namespace) -> None:
    tree = assemble(Path(args.archive), Path(args.vendored), Path(args.official), Path(args.work))
    _, patches = patch_order(tree)
    q_final = patch_order(tree)[0]
    rows: list[dict[str, object]] = []
    for k in range(len(patches) + 1):
        for width in (0, q_final):
            out = Path(args.work) / f"prefix_{k:02d}_w{width}.json"
            cmd = [
                sys.executable,
                __file__,
                "prefix",
                "--tree",
                str(tree),
                "--upto",
                str(k),
                "--width",
                str(width),
            ]
            proc = subprocess.run([*cmd, "--out", str(out)], capture_output=True, text=True)
            if proc.returncode == 0:
                rows.append(json.loads(out.read_text()))
            else:
                name = "base" if k == 0 else patches[k - 1]
                rows.append(
                    {"upto": k, "patch": name, "width_limit": width or None, "error": proc.stderr[-400:]}
                )
            print(json.dumps(rows[-1]), flush=True)
    Path(args.out).write_text(json.dumps(rows, indent=1) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["assemble", "prefix", "ledger"])
    ap.add_argument("--archive")
    ap.add_argument("--vendored")
    ap.add_argument("--official")
    ap.add_argument("--work")
    ap.add_argument("--tree")
    ap.add_argument("--upto", type=int, default=0)
    ap.add_argument("--width", type=int, default=0, help="declared qubit limit (0: the patch's own)")
    ap.add_argument("--out")
    args = ap.parse_args()
    if args.mode == "assemble":
        print(assemble(Path(args.archive), Path(args.vendored), Path(args.official), Path(args.work)))
    elif args.mode == "prefix":
        try:
            row = build_prefix(Path(args.tree), args.upto, args.width or None)
        except Exception:
            traceback.print_exc()
            raise SystemExit(1) from None
        Path(args.out).write_text(json.dumps(row) + "\n")
    else:
        ledger(args)


if __name__ == "__main__":
    main()
