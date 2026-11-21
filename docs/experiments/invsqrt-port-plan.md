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

## Stage B result (2026-11-19): the traced closure

The owner approved one container build of the invsqrt builder (2026-11-19). `scripts/invsqrt_reference_build.sh` runs his `build.sh`
inside the rootless podman container used for DQI (no network, source read-only, glibc 2.39 image, CPython 3.13.13 with numpy
2.2.4, the competition `kickmix.so` and verifier mounted read-only; their pinned SHA-256 both matched our `data/`). A
`sitecustomize.py` audit hook in the venv logged every file opened and every code object executed.

Result [M], twice (63 s and 65 s each, exact full-domain proof `PASS_EXACT_NATIVE_TEXT_ALL_REQUESTED_INPUTS_ALL_HMR_TRANSCRIPTS`):
`BUILT invsqrt.kmb 321aff83636214196daa9cbc9dcc9c5e12a155bcff8d9989e98b8cee40935177`, byte-identical to the dataset's circuit.

| | files | bytes |
|---|---:|---:|
| source archive | 556 | 18.5 MB |
| Python files in the archive | 255 | |
| found by a name-based static import scan | 19 | |
| **Python files executed by the build** | **78** | **536 KB** |
| non-Python files opened (mostly hash-checked pinned data, loader certificates) | 302 | 16.3 MB |
| executed files that are not in the archive | 0 | |

The 78 modules: the generator entry (`tools/build_variant.py`, `tools/macrun.py`), the 14 patch modules and `agents/composer/p/w2core_e2.py`,
and the pinned `candidate01`, `candidate06`, `candidate07`, `arithmetic_round2` and `checkpoint002/cleanroom` base modules.
The lists are `docs/experiments/data/invsqrt_v12_executed_py.txt` and `invsqrt_v12_opened_data.txt` (paths only).
The 302 data files include every pinned file the sources hash-check, so they over-count what the port needs; which are read for
content (tables, loader certificates) is the next narrowing.

## Stage C0 and C1 (2026-11-19): vendored closure and our wiring

C0: the 78 executed modules are vendored under `third_party/syed_invsqrt/` (`docs/log/entries/2026-11-19-invsqrt-vendored.md`).
C1: `src/invsqrt_gen/port/stages.py` (our code) assembles the work tree (archive data, vendored files checked byte-equal,
relocation token, host `kickmix.so` and verifier), then builds every prefix of the 13 patches, one process per prefix, through the
vendored `build_variant.build()` and reports qubits, exact mean Toffolis, rotations and the modelled cost. It runs in the
same sandbox as the reference build (`scripts/invsqrt_port_stages.sh`, about 9 s per build). Data:
`docs/experiments/data/invsqrt_port_ledger.json`. [M]

| k | patch | width | qubits | mean Toffolis | modelled cost | step | ratio |
|---:|---|---|---:|---:|---:|---:|---:|
| 0 | `(base candidate10)` | own (48) | 48 | 1,548.75 | 85,469 |  | 24.30 |
| 1 | `patch_fwd_narrow` | own (48) | 48 | 1,548.25 | 85,445 | -24 | 24.31 |
| 2 | `patch_w47_body` | own (48) | 48 | 1,544.57 | 85,268 | -177 | 24.36 |
| 3 | `patch_endpoint_v9e2` | own (48) | 48 | 1,520.57 | 84,116 | -1,152 | 24.69 |
| 4 | `patch_hret_sat_s15k7a` | own (48) | 48 | 1,511.07 | 83,660 | -456 | 24.82 |
| 5 | `patch_seedinv` | own (48) | 48 | 1,505.07 | 83,372 | -288 | 24.91 |
| 6 | `patch_coefdisp` | own (48) | 48 | 1,505.07 | 83,372 | +0 | 24.91 |
| 7 | `patch_coef2_q46` | own (48) | 48 | 1,506.07 | 83,420 | +48 | 24.90 |
| 8 | `patch_h2ret` | own (48) | 48 | 1,505.57 | 83,396 | -24 | 24.90 |
| 9 | `patch_proddisp` | own (48) | 48 | 1,505.57 | 83,396 | +0 | 24.90 |
| 11 | `patch_ld_first20_56b8` | own (48) | 48 | 1,500.57 | 83,156 | -240 | 24.97 |
| 12 | `patch_second46_c19_70nb1` | own (48) | 48 | 1,491.57 | 82,724 | -432 | 25.10 |
| 12 | `patch_second46_c19_70nb1` | 46 | 46 | 1,521.57 | 80,657 |  | 25.75 |
| 13 | `patch_q47_decoder_resynth2` | own (48) | 48 | 1,489.57 | 82,628 |  | 25.13 |
| 13 | `patch_q47_decoder_resynth2` | 46 | 46 | 1,519.57 | 80,565 |  | 25.78 |

`cost` is the modelled `Q * (Toffolis + T/4 + rotation charge)`, not measured; the ratio is against the paper reference
2,076,774. Findings:

1. **The wiring works**: the full 13-patch build at width 46 gives 46 qubits, 1,519.57 Toffolis, modelled cost 80,565 (25.78x).
   The reference circuit is 80,162.76 (1,511.57 Toffolis, 25.91x); the 0.5% difference is the mechanical finishing passes of
   `tools/pipeline.sh` (affine audit, hold pass, `Z_POW` merging) and the post pass `relocate_cs2`, which our wiring does not yet run.
2. **Most of the quality is in the base, not the patches.** The unpatched base `candidate10` is already 48 qubits at 24.30x; the
   13 patches add 3.3% in cost at width 48. The largest steps: `endpoint_v9e2` (-1,152, the ring endpoint with hold/measure-release),
   `hret_sat` (-456), `second46_c19` (-432), `seedinv` (-288), `ld_first20` (-240). The 2-qubit narrowing to 46 (cost -2,000 at the
   last steps, 2.4%) is bought with +30 Toffolis, so the width patches pay.
3. **Prefixes are not independent.** At width 46, prefixes 0 to 11 do not build (the width is declared at 48 until the width patches), and prefix 10
   (`donor_first60`) needs a plan file that import-time code of a later patch supplies: the reference build loads all 13 patch
   modules before applying any. Per-patch deltas are therefore valid at width 48 only, except for prefix 10, which has none.

## Plan

* Stage A, B, C0, C1: done (above).
* Stage C2: done 2026-11-20. Our wiring runs the finishing passes and reproduces `321aff83` byte for byte, with a ledger row per pass
  (`scripts/invsqrt_port_finish.sh`, `docs/experiments/data/invsqrt_port_finish.json`; [log](../log/entries/2026-11-20-invsqrt-port-finish.md)). [M]
* Stage D: S3 (exact optimisation of tables and loaders) on top of the working port.
* Not covered: the 44-qubit circuits of v13 (no source; the dataset dropped the archives).

## v17 line (2026-11-21)

The 43-qubit circuit `70fe5f79` (28.67x, in `best/`) has a generator we hold. Its sandboxed build reproduces it byte for byte (178 executed stage modules, 43 builder files; [log](../log/entries/2026-11-21-invsqrt-v17-reference-build.md)). Next: vendor the closure, wire our own driver stage by stage, ledger per stage, byte identity. The v12 work above remains the template for the wiring.

Stage C0 (vendoring the 220 executed modules) and C1 (our driver `src/invsqrt_gen/port/v17.py`, `scripts/invsqrt_v17_port.sh`, byte-identical to `70fe5f79` with a ledger row per stage) are done ([driver log](../log/entries/2026-11-22-invsqrt-v17-driver.md)). Next: exchange rates per stage and the finishing passes on our own circuits.
