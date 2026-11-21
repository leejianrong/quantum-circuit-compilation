"""Our driver for syed3000's v17 invsqrt generator (the 43-qubit line, ``70fe5f79``).

Runs inside the sandbox of ``scripts/invsqrt_v17_port.sh`` (CPython 3.13 with numpy and SciPy, the competition
``kickmix`` module on ``PYTHONPATH``). Standard library plus what the vendored modules import.

It does what the generator's own ``build.py`` does, with three differences: it is our code, every stage gets a
ledger row (seconds, export hash, and for kmx candidates the exact expectation and modelled cost), and the two
packaging repairs the Kaggle download needs are explicit. The download stores the generator expanded, so
``syed_source`` is copied instead of unzipped, and every ``*.json.gz`` witness was stored decompressed, so a
gzip sibling is made for each one the sources mention (they only read the content).
``third_party/syed_invsqrt_v17/src`` holds the 220 executed modules; the assembled tree is the download,
checked byte-equal to them.

    v17.py build --gen G --vendored V/src --work W --out O
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

WANT = "70fe5f79d56bd48cd8fc9602757a0520b4d11859967627906cccb3dec25b7692"
RT = Path("incumbent_sources/frozen_source/fusion/runtime")
OLD_ROOT = "/workspace/scratch/394c5ff892d3/recovered/candidate32/research/fusion/runtime"
OLD_MAC = "/Users/asad.ali/codex quantum/fusion3_reduced_anchor/reference_build/"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assemble(gen: Path, vendored: Path, work: Path) -> tuple[Path, Path]:
    """Copy the download, check the vendored files equal it, make the gzip siblings, copy ``syed_source``."""
    here = work / "gen"
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(gen, here)
    for f in sorted(p for p in vendored.rglob("*") if p.is_file()):
        rel = f.relative_to(vendored)
        if (here / rel).read_bytes() != f.read_bytes():
            raise SystemExit(f"vendored file differs from the download: {rel}")
    names: set[str] = set()
    for f in here.rglob("*"):
        if f.is_file() and f.suffix in {".py", ".json", ".md"}:
            names.update(re.findall(r"([A-Za-z0-9_.\-]+\.json)\.gz", f.read_text(errors="ignore")))
    for f in list(here.rglob("*.json")):
        gz = f.with_name(f.name + ".gz")
        if f.name in names and not gz.exists():
            with gzip.GzipFile(gz, "wb", mtime=0) as g:
                g.write(f.read_bytes())
    stages = work / "stages"
    shutil.copytree(here / "syed_source", stages)
    return here, stages


def cost_row(runtime: Path, kmx: Path) -> dict[str, object]:
    """Exact expectation and modelled cost of a kmx candidate through the generator's own cost code."""
    engine = runtime / "work/c10/narrow/checkpoint002/cleanroom/baseline_stage97"
    for p in (engine / "engine", engine / "tests", runtime / "tools"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    os.environ.setdefault("FG", str(runtime))
    os.environ.setdefault("NARROW", str(runtime / "work/c10/narrow"))
    km = importlib.import_module("kickmix")

    bv = importlib.import_module("build_variant")
    text = kmx.read_text()
    resources = importlib.import_module("fourier_resource_expectation").exact_expectation(text)
    q = km.Circuit(text).num_qubits
    model = bv.cost_model(resources, q)
    return {
        "qubits": q,
        "toffoli_like": model["toffoli_like"],
        "T": model["T"],
        "generic_rotations": model["generic_rotations"],
        "modelled_cost": model["modelled_cost"],
    }


def build(args: argparse.Namespace) -> None:
    km = importlib.import_module("kickmix")

    work, out = Path(args.work).resolve(), Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    here, stages = assemble(Path(args.gen), Path(args.vendored), work)
    runtime = stages / RT
    dag = json.loads((stages / "dag.json").read_text())
    release = json.loads((stages / "original.json").read_text())
    macro = next(stages.rglob("*.kmx.macro"))
    macro.rename(macro.with_suffix(""))
    for f in stages.rglob("*.py"):
        s = f.read_text()
        n = s.replace(OLD_ROOT, str(runtime)).replace(OLD_MAC + str(RT), str(runtime))
        if s != n:
            f.write_text(n)
    sys.path.insert(0, str(here))
    importlib.import_module("prepare").prepare(stages)  # vendored, found on the path above
    logs = stages / "logs"
    logs.mkdir()
    temp = stages / "temp"
    temp.mkdir()
    env = {k: v for k, v in os.environ.items() if k not in ("FUSION_SOURCE_PROJECT", "FUSION_SOURCE_RUNTIME")}
    env.update(TMPDIR=str(temp), XDG_CACHE_HOME=str(temp / "cache"), MPLCONFIGDIR=str(temp / "matplotlib"))
    env.update(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", VECLIB_MAXIMUM_THREADS="1")
    env.update(NUMBA_NUM_THREADS="1", PYTHONDONTWRITEBYTECODE="1", SYED_SOURCE_ROOT=str(stages))
    engine = runtime / "work/c10/narrow/checkpoint002/cleanroom/baseline_stage97"
    paths = [
        here,
        engine / "engine",
        engine / "tests",
        stages / "restored/research_v9/second_seed_and_phases",
    ]
    env["PYTHONPATH"] = os.pathsep.join(map(str, [*paths, Path(str(km.__file__)).resolve().parent]))
    rows: list[dict[str, object]] = []

    def flush() -> None:
        (out / "ledger.json").write_text(json.dumps(rows, indent=1) + "\n")

    def run(name: str, cmd: list[str], cwd: Path, extra: dict[str, str] | None = None) -> float:
        print(name, flush=True)
        t0 = time.monotonic()
        with (logs / (name + ".log")).open("w") as f:
            r = subprocess.run(cmd, cwd=cwd, env={**env, **(extra or {})}, stdout=f, stderr=subprocess.STDOUT)
        if r.returncode:
            raise SystemExit(f"{name} failed\n" + (logs / (name + ".log")).read_text()[-2000:])
        return round(time.monotonic() - t0, 1)

    for j, stage in enumerate(dag["stages"]):
        name = stage["id"]
        dst = stages / f"_build/{j:02}_{name}"

        def subst(v: str, dst: Path = dst) -> str:
            return (
                v.replace("{ROOT}", str(stages))
                .replace("{OUT}", str(dst))
                .replace("{PYTHON}", sys.executable)
            )

        cwd = Path(subst(stage["cwd"]))
        cwd.mkdir(exist_ok=True, parents=True)
        seconds = run(
            name,
            [subst(o) for o in stage["argv"]],
            cwd,
            {k: subst(v) for k, v in stage["environment"].items()},
        )
        for exp in stage["exports"]:
            made = dst / exp["generated"]
            got = sha256(made)
            if got != exp["expected_sha256"]:
                raise SystemExit(f"{name}: export {made} has {got}, expected {exp['expected_sha256']}")
            to = stages / exp["destination"]
            to.parent.mkdir(exist_ok=True, parents=True)
            shutil.copyfile(made, to)
            row: dict[str, object] = {
                "stage": j,
                "id": name,
                "seconds": seconds,
                "export": exp["destination"],
                "sha256": got,
            }
            if to.suffix == ".kmx":
                try:
                    row.update(cost_row(runtime, to))
                except Exception as err:  # the cost is a report; the hash check above is the gate
                    row["cost_error"] = f"{type(err).__name__}: {err}"[:200]
            rows.append(row)
            print(json.dumps(row), flush=True)
        flush()
    logical, packed = stages / "logical", stages / "physical"
    t_meta = run(
        "metadata",
        [
            sys.executable,
            "-B",
            str(stages / release["metadata_emitter"]),
            "--out",
            str(logical),
            "--build-only",
        ],
        stages,
    )
    rows.append({"stage": "metadata", "seconds": t_meta})
    t_pack = run(
        "packing",
        [
            sys.executable,
            "-B",
            str(stages / "root/pack_actual_q43_native.py"),
            "--native",
            str(logical / "candidate_text.kmx"),
            "--out",
            str(packed),
            "--expected-native-sha256",
            release["logical_native_sha256"],
        ],
        stages,
    )
    if sha256(packed / "candidate_text.kmx") != release["physical_native_sha256"]:
        raise SystemExit("packed native text differs from the release record")
    circuit = km.Circuit.from_file(str(packed / "candidate_text.kmx"), format="kmx")
    circuit.to_file(str(stages / "original.kmb"), format="kmb")
    if sha256(stages / "original.kmb") != release["circuit_sha256"]:
        raise SystemExit("original Q43 circuit hash differs from the release record")
    rows.append(
        {
            "stage": "original_q43",
            "seconds": t_pack,
            "sha256": release["circuit_sha256"],
            **cost_row(runtime, packed / "candidate_text.kmx"),
        }
    )
    flush()
    optimize = importlib.import_module("finish_f16").optimize
    rebuild_f16 = importlib.import_module("owner_lineage").build

    t0 = time.monotonic()
    parent = rebuild_f16(
        stages / "original.kmb",
        stages / "incumbent_sources/frozen_source/fusion64/native_angles.json",
        out / "lineage_stages",
    )
    rows.append(
        {
            "stage": "lineage_f16plus",
            "seconds": round(time.monotonic() - t0, 1),
            "sha256": sha256(parent),
        }
    )
    flush()
    t0 = time.monotonic()
    fitted = optimize(parent.with_suffix(".kmx").read_text(), out / "verified_cuts")
    km.Circuit(fitted).to_file(str(out / "invsqrt.kmb"), format="kmb")
    final = sha256(out / "invsqrt.kmb")
    (out / "invsqrt.kmx").write_text(fitted)
    rows.append(
        {
            "stage": "finish_f16",
            "seconds": round(time.monotonic() - t0, 1),
            "sha256": final,
            "matches_70fe5f79": final == WANT,
        }
    )
    flush()
    print(json.dumps(rows[-1]), flush=True)
    if final != WANT:
        raise SystemExit(f"not byte-identical: got {final}")
    print(f"BYTE-IDENTICAL {final}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["build"])
    ap.add_argument("--gen", required=True)
    ap.add_argument("--vendored", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--out", required=True)
    build(ap.parse_args())


if __name__ == "__main__":
    main()
