# invsqrt: staged port plan for syed3000's 44-qubit line (QCC-68)

Method as for DQI (`docs/experiments/dqi-syed-decode.md`): vendor the import closure byte-identically under
`third_party/`, write our own wiring outside it, record per-stage deltas, verify with the official verifier. Source read:
v12 archive `invsqrt_source_zip` (Apache-2.0, PROVENANCE S14), unpacked with a path-checked `zipfile` into its own directory
and read only. The v13 dataset dropped the archives, so v12 builds the 46-qubit circuit (80,162.76, 25.91x); the 44-qubit
v13 circuit (75,170.65) and koushik's 74,797.40 (in `best/`) have no source we hold. The port therefore targets the
46-qubit line first and treats 44 qubits as a later delta.

## What the builder is [V]

* 561 files, 255 Python files, 43k lines, 18.6 MB (most of the weight is research JSON and prebuilt `.kmb`/`.kmx`).
* `build.sh` copies the tree to a work dir, copies the competition `kickmix.so` and verifier next to the pinned tree (their
  SHA-256 are checked), then runs `tools/build_variant.py --Q 46` with 13 `--patch` modules in `patches/PATCH_ORDER.txt`
  order, then `tools/pipeline.sh` (mechanical passes, compile `.kmx` to `.kmb`, exact full-domain proof), then one
  post pass (`relocate_cs2.py`), then a SHA-256 check. Needs CPython 3.13 with numpy.
* `build_variant.py` is "candidate10's `generate.build()` step for step" with patches that **rebind attributes on live
  modules** (`ctx.components['root'] = ...`, `ctx.baseline.seed_forward = ...`). The pinned base files on disk stay
  byte-identical so their hash checks pass. Modules are found by `sys.path.insert` and `spec_from_file_location`, so
  a name-based static import closure finds only 19 files; the true closure needs a runtime import trace.

## Stages = the patch order

| # | Patch | What it changes (from `docs/experiments/invsqrt-syed-decode.md`) | Ledger to record |
|---|---|---|---|
| 0 | base `candidate10` build | the pinned baseline generator | qubits, mean Toffolis, rotations |
| 1 | `fwd_narrow` | pair normaliser forward, 18 prefix ANDs | delta Q, delta T |
| 2 | `w47_body` | new `emit_body`: the whole stage order at Q47/48 | |
| 3 | `endpoint_v9e2` | ring endpoint, hold/measure-release CSWAP pairs | |
| 4 | `hret_sat_s15k7a` | retained history rebuilds | |
| 5 | `seedinv` | seed inverse | |
| 6 | `coefdisp` | coefficient dispose | |
| 7 | `coef2_q46` | second coefficient | |
| 8 | `h2ret` | H2 retire | |
| 9 | `proddisp` | product carries freed | |
| 10 | `donor_first60` | donor tails | |
| 11 | `ld_first20_56b8` | first loader (56 Toffolis, cap 20) | |
| 12 | `second46_c19_70nb1` | second loader (70, cap 19) | |
| 13 | `q47_decoder_resynth2` + `endpoint_walk8`, `q46_loaders` | decoder resynthesis | |
| post | `relocate_cs2` | -1 Toffoli | |

Cumulative application (patch k with patches 1..k-1) gives the per-stage ledger, the same way `src/dqi_gen/stages.py`
does for DQI. Every stage must pass the exact proof (`tools/prove_any.py`, full domain) before its delta counts, and the
final circuit goes through the official verifier at 10 salts.

## Blockers and the owner decisions they need

1. **Runtime closure.** To vendor exactly what is imported we need a trace of one build. Running his `build.sh` is a
   third-party builder run, which the standing rules forbid except in the sandboxed container route. A static plus
   path-string scan is the alternative and is slower and less certain. Decision: may the container route
   (`scripts/dqi_reference_build.sh` pattern) be used once for the invsqrt builder, to trace imports and check the byte
   hash? This is the question already open in `docs/knowledge/open-questions.md`.
2. **kickmix.so.** The pinned sources check the SHA-256 of the competition `kickmix.so` (`c66b3216...`) and the proof
   pipeline loads it; it needs a newer libstdc++ than this WSL has, so stages must be proved on Kaggle (like DQI) or in the
   container.
3. **Python 3.13.** The build asserts CPython 3.13; this repo uses 3.12 to 3.14. Vendored modules would be wired from our
   own code on our interpreter, so this only matters for the byte-identical reference build.
4. **Missing source for the 44-qubit line.** See above.

## Plan

* Stage A (no decision needed): inventory by static and path-string scan, list of base modules under
  `work/c10/narrow/arithmetic_round2/native/candidate10` and what each patch touches.
* Stage B (needs decision 1): reference build in the container, trace, byte hash, per-patch deltas on Kaggle.
* Stage C: vendor, own wiring (`src/invsqrt_gen/port/`), per-stage deltas, proof, official verify.
* Stage D: S3 (exact optimisation of tables and loaders) on top of the working port.
