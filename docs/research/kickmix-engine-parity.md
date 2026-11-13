# kickmix-engine parity with the official verifier (QCC-53)

Engine: [kickmix-engine](https://github.com/manwithacat/kickmix-engine) at `166b61d2e0a7404ace8acf62a6f269105e6b97f1`,
built from audited source ([audit](kickmix-engine-audit.md)). Result: **identical to the official verifier on every
case tried**, so we added an opt-in screening path (`bench verify --engine kickmix-engine`,
[docs/MEASUREMENT.md](../MEASUREMENT.md)). It is still screening only: ADR-0001 keeps the official verifier as the
only gate, and the ledger tags engine rows `kind=screen`.

## Method

Each case ran the official verifier and the engine on the same circuit, salt and (for DQI) instance size, under
`flock /tmp/qcc-heavy.lock`, and compared the whole JSON each prints, field by field. Salts are the ledger's
`salt_for(i)` strings. The official run was either `bench verify` (invsqrt) or the host verifier's own CLI
(`verify_submission_dqi.py`, `verify_submission_invsqrt.py`, `dfthcsos/verify.py`), both with pip kickmix. Engine
machine: AVX2 kernel (this CPU has no AVX-512), 16 threads. "Exact" means every printed field is equal, including the
float score to the last digit, the failure message text and the statistics in it.

| Task | Circuits | Salts | Pass cases | Fail cases | Exact |
|---|---|---|---|---|---|
| invsqrt | our verified `best/` circuit, the competition sample, a generator circuit (`invsqrt_gen`, a=7), a too-coarse generator circuit (phase tolerance fails), 8 broken variants of the best circuit | 0 to 5 | 7 | 9 | 16 of 16 |
| dfthcsos | our `best/` submission, the competition sample, 5 broken variants of one `angle_k` file | 0 to 2 | 4 | 5 | 9 of 9 |
| DQI (small fields: tiny, small, medium; 1 792 shots) | `dqi_gen` reference and divstep decoders, the lanczos decoder (fails at that shot count), 5 broken variants of divstep small | 0 to 3 | 24 | 9 | 33 of 33 |

Total 58 comparisons, 58 exact (pass/fail, cost, message, exit code). Full-size DQI circuits were not loaded: they
need 5 to 9 GB and this machine has 7 GB (ADR-0002).

Broken variants (all made by editing the text form and rewriting `.kmb` with `format='kmb'`): one `CX` turned into
`CZ`, one `CX` turned into `X`, one Toffoli dropped (early and late), one `CZ` dropped, a final `X` on the input
register dropped, a rotation angle scaled by 1.5, and a stray `X` on a scratch qubit appended. Failure classes seen,
all with the official message text: `x was not restored`, `phase error ... exceeds tolerance` (twice, one with the
rotation-angle change at 6.003e-10 against 5.859e-10), `Scratch qubit q40 did not return to |0>`, DQI
`Effective error rate ... (value_errors=889/1792, phase_errors=0/1792)` with identical counts, and for dfthcsos
`uncorrected phase (measurement kickback)`, `workspace qubits are not returned to |0>` and the energy-error message.
Two DQI variants (a dropped trailing `CX`, a dropped early Toffoli) still pass officially and in the engine, with the
same cost: they are not failures on the sampled inputs, which is itself agreement. Twelve of the invsqrt comparisons
(3 salts of the best circuit, the sample, 8 variants) used official results from `bench verify` itself.

## Speed

Wall time per salt on a 16-core machine shared with other agents (load average 17 to 28, so absolute times are
noisy). Cleanest back-to-back pairs, nothing else of ours running:

| Case | Official | Engine | Ratio |
|---|---|---|---|
| invsqrt best circuit, salt 3 | 178.8 s | 18.3 s | 9.8x |
| invsqrt best circuit, salt 4 | 175.6 s | 18.0 s | 9.8x |
| invsqrt generator circuit (a=7), salt 5 | 145.9 s | 30.4 s | 4.8x |
| dfthcsos best, salts 1 and 2 (program and FCIDUMP caches warm) | 43.5 s, 45.7 s | 9.1 s, 8.4 s | about 5x |
| DQI small instances | 0.4 to 1.9 s | 0.3 to 1.1 s | startup bound, about 1.5x |

The first run of a circuit costs more (compile and cache write): the best invsqrt circuit took 27 to 40 s on its first
salts and 18 s once the program cache was warm. Failing circuits stop early in both and take 3 to 7 s either way.
The claimed 7 to 10x holds for invsqrt; it is smaller for the generator circuit and dfthcsos.

## What this does not show

- Agreement on circuits we have not tried. Re-run this comparison (the `--cross-check` flag of the engine does it per
  run) on any new engine commit, and spot-check with the official verifier for anything that matters.
- Full-size DQI parity (not loadable here). The engine's own tests cover it and the DQI small-field results agree.
- Anything about the official verifier's hidden salts. The engine is deterministic given a salt, as is the official
  one, so a salt-dependent failure shows up in both or neither.

Decision: use the engine for invsqrt and dfthcsos iteration and for salt sweeps; every candidate still gets the
official verifier at several salts before promotion.
