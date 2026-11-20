"""Our wiring of the vendored v12 invsqrt builder: assemble its tree, build every prefix of the patches.

Runs inside the sandbox of ``scripts/invsqrt_port_stages.sh`` (CPython 3.13 with numpy and the
competition ``kickmix.so``, which this host cannot load). Standard library only.
``third_party/syed_invsqrt/src`` holds the 78 files the reference build executes; the rest of the
work tree (pinned data, certificates) comes from the downloaded archive, an input (QCC-68).

    stages.py assemble --archive A/src --vendored V/src --official DATA --work W
    stages.py prefix --tree T --upto K --out F.json
    stages.py ledger --archive A/src --vendored V/src --official DATA --work W --out L.json
    stages.py finish --archive A/src --vendored V/src --official DATA --work W --out F.json

A patch rebinds attributes of live modules, so every prefix runs in its own process. Prefix 0 is the unpatched
base (``candidate10``); prefix K applies the first K ``patch`` lines of ``patches/PATCH_ORDER.txt``.
"""

from __future__ import annotations

import argparse
import hashlib
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


PASS_STATUS = "PASS_EXACT_NATIVE_TEXT_ALL_REQUESTED_INPUTS_ALL_HMR_TRANSCRIPTS"
WANT_SHA = "321aff83636214196daa9cbc9dcc9c5e12a155bcff8d9989e98b8cee40935177"
# overrides his generator reads from the environment; build.sh unsets them
GENERATOR_OVERRIDES = (
    "DIVIDER_FORCE_CAP",
    "DIVIDER_PLACEHOLDER",
    "DIVIDER_RETIRE",
    "LD_FIRST_JSON",
    "LEAD_SECOND_JSON",
    "TK46_SECOND_JSON",
    "W2_E_HOLD",
    "W2_F_HOLD",
    "W2_R2",
    "W2_V10_G1",
    "W2_V9_FORM",
    "W2_V9_PLACEHOLDER",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_raw(tree: Path, out: Path) -> None:
    """The generator step of his build.sh: all patches at the declared width, raw kmx text and kmb."""
    os.environ["FG"] = str(tree)
    os.environ["NARROW"] = str(tree / "work" / "c10" / "narrow")
    os.chdir(tree)
    sys.path.insert(0, str(tree / "tools"))
    bv = importlib.import_module("build_variant")
    q, patches = patch_order(tree)
    patchset = bv.PatchSet([bv.load_patch(str(tree / "patches" / n)) for n in patches])
    _ctx, circuit, text, _cuts, _trace, _layout = bv.build(patchset, q)
    out.with_suffix(".kmx").write_text(text)
    circuit.to_file(str(out.with_suffix(".kmb")), format="kmb")


def cost_row(tree: Path, name: str, kmx: Path, q: int) -> dict[str, object]:
    """Exact expectation and modelled cost of a kmx text (qubit count fixed at the declared width)."""
    sys.path.insert(0, str(tree / "tools"))
    stage97 = tree / "work/c10/narrow/checkpoint002/cleanroom/baseline_stage97"
    sys.path[:0] = [str(stage97 / "tests"), str(stage97 / "engine")]
    bv = importlib.import_module("build_variant")
    resources = importlib.import_module("fourier_resource_expectation").exact_expectation(kmx.read_text())
    model = bv.cost_model(resources, q)
    return {
        "pass": name,
        "kmx_sha256": sha256(kmx),
        "toffoli_like": model["toffoli_like"],
        "T": model["T"],
        "generic_rotations": model["generic_rotations"],
        "modelled_cost": model["modelled_cost"],
    }


def finish(args: argparse.Namespace) -> None:
    """Our wiring of pipeline.sh and post_inplace.sh: each pass is its own process with a ledger row."""
    work = Path(args.work)
    tree = assemble(Path(args.archive), Path(args.vendored), Path(args.official), work)
    q, _ = patch_order(tree)
    env = {
        **os.environ,
        "FG": str(tree),
        "NARROW": str(tree / "work" / "c10" / "narrow"),
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
    }
    for k in GENERATOR_OVERRIDES:
        env.pop(k, None)
    t = tree / "tools"
    out = work / "final"
    out.mkdir(exist_ok=True)
    name = "s15k7a"
    rows: list[dict[str, object]] = []

    def run(label: str, script: Path, *a: str, log: str | None = None, shim: bool = False) -> None:
        cmd = [sys.executable, *([str(t / "macrun.py")] if shim else []), str(script), *a]
        t0 = time.monotonic()
        proc = subprocess.run(cmd, cwd=tree, env=env, capture_output=True, text=True)
        (out / (log or label + ".log")).write_text(proc.stdout + proc.stderr)
        if proc.returncode:
            raise SystemExit(f"{label} failed:\n{proc.stderr[-600:]}")
        rows.append({"pass": label, "seconds": round(time.monotonic() - t0, 1)})
        print(json.dumps(rows[-1]), flush=True)

    def record(label: str, kmx: Path) -> None:
        rows[-1].update(cost_row(tree, label, kmx, q))
        print(json.dumps(rows[-1]), flush=True)

    raw = work / "build" / (name + "raw")
    raw.parent.mkdir(exist_ok=True)
    proc = subprocess.run(
        [sys.executable, __file__, "raw", "--tree", str(tree), "--out", str(raw)],
        env=env,
        capture_output=True,
        text=True,
    )
    if proc.returncode:
        raise SystemExit(proc.stderr[-600:])
    rows.append({"pass": "generator"})
    raw_kmx = raw.with_suffix(".kmx")
    record("generator", raw_kmx)

    run(
        "s1.audit_affine",
        t / "audit_affine.py",
        str(raw_kmx),
        "--out",
        str(out / "s1.audit.json"),
        log="s1.audit.log",
    )
    run(
        "s1.audit_pairs",
        t / "audit_pairs.py",
        str(raw_kmx),
        "--live",
        str(out / "s1.audit.live.npy"),
        "--out",
        str(out / "s1.pairs.json"),
        log="s1.pairs.log",
    )
    run(
        "s2.hold_pass",
        t / "hold_pass.py",
        str(raw_kmx),
        str(out / "s1.pairs.json"),
        "--out",
        str(out / "s2.kmx"),
        "--Q",
        str(q),
        log="s2.hold.log",
    )
    record("s2.hold_pass", out / "s2.kmx")
    cur = out / "s2.kmx"
    for rnd in range(1, 5):
        audit = out / f"r{rnd}.audit.json"
        run(
            f"r{rnd}.audit_affine",
            t / "audit_affine.py",
            str(cur),
            "--out",
            str(audit),
            log=f"r{rnd}.audit.log",
        )
        n = len(json.loads(audit.read_text())["findings"])
        rows[-1]["findings"] = n
        if n == 0:
            break
        nxt = out / f"r{rnd}.kmx"
        run(f"r{rnd}.postpass", t / "postpass.py", str(cur), str(audit), "--out", str(nxt))
        record(f"r{rnd}.postpass", nxt)
        cur = nxt
    zp = out / "zpow.kmx"
    run("zpow.merge_zpow", t / "merge_zpow.py", str(cur), "--out", str(zp), log="zpow.log")
    record("zpow.merge_zpow", zp)
    final = out / "final_text.kmx"
    shutil.copy(zp, final)
    kmb = out / (name + ".kmb")
    run("compile", t / "kmx_to_kmb.py", str(final), "--out", str(kmb), log="compile.log", shim=True)
    run(
        "prove",
        t / "prove_any.py",
        "--circuit",
        str(kmb),
        "--out",
        str(out / (name + ".proof.json")),
        log="prove.log",
        shim=True,
    )
    rows[-1]["kmb_sha256"] = sha256(kmb)
    pre = out / "final_text_precs.kmx"
    shutil.copy(final, pre)
    run(
        "post.relocate_cs2",
        tree / "agents" / "micro47" / "scripts" / "relocate_cs2.py",
        str(pre),
        str(final),
        log="post.log",
    )
    record("post.relocate_cs2", final)
    run("compile_post", t / "kmx_to_kmb.py", str(final), "--out", str(kmb), log="compile_post.log", shim=True)
    run(
        "prove_post",
        t / "prove_any.py",
        "--circuit",
        str(kmb),
        "--out",
        str(out / (name + ".proof.json")),
        log="prove_post.log",
        shim=True,
    )
    proof = json.loads((out / (name + ".proof.json")).read_text())
    got = sha256(kmb)
    rows[-1].update(
        {
            "kmb_sha256": got,
            "proof_status": proof["status"],
            "proved_inputs": proof["proved_inputs"],
            "matches_reference": got == WANT_SHA and proof["status"] == PASS_STATUS,
        }
    )
    print(json.dumps(rows[-1]), flush=True)
    Path(args.out).write_text(json.dumps(rows, indent=1) + "\n")
    if got != WANT_SHA or proof["status"] != PASS_STATUS:
        raise SystemExit(f"not byte-identical: got {got}")
    print(f"BYTE-IDENTICAL {got}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["assemble", "prefix", "ledger", "finish", "raw"])
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
    elif args.mode == "raw":
        build_raw(Path(args.tree), Path(args.out))
    elif args.mode == "finish":
        finish(args)
    else:
        ledger(args)


if __name__ == "__main__":
    main()
