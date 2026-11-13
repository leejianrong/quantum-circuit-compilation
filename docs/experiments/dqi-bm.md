# DQI: a dialog-free Berlekamp-Massey decoder (QCC-19, E036)

Stage 2 route chosen after the Szego analysis (`docs/experiments/dqi-stage2.md`): build the published idea of a Berlekamp-Massey
decoder whose history is reconstructed instead of stored (Gu, Kemeny, Yelin, Lukin, arXiv:2610.22367 SI I.1; the
andigu/uncompute repository states Apache-2.0, nothing was copied from it; the public DQI circuit lineage has no licence).
Code: `src/dqi_gen/bm.py` (circuit), `src/dqi_gen/bmref.py` (classical reference), `tests/unit/test_dqi_bm.py`.
It is our divstep decoder (`decoder.py`) with the 945-qubit dialog replaced, so normalisation, Omega in place, the Forney scan
and their undoing are shared.

## Construction (derived for our rows, checked classically before building)

State: sigma row `g`, template row `f` (shifted up by `z` each step, frozen once its top coefficient is nonzero), scalar `b`, counter `delta`.

1. **Ties replace.** Swap when `delta >= 0` and `d != 0` (threshold moved from `> 0`). Generic inputs then never take a "retain"
   step (no swap with `d != 0`): the first measurement gave 3 retain steps in 300 weight-law shots, against about half of all
   steps with the old rule.
2. **Invariant** `g[0] * b = 1`. The shifted template has `f[0] = 0`, so after a swap step `f[0] = g_old[0] != 0`: a swap is
   recognised from the after-state by `f[0] != 0` (11 Toffolis, cleared by measurement), and its quotient is `c = 1 / (f[0] b)`, so
   neither the swap bit nor `c` is stored (`bmref.py` asserts both identities at every step of 100 weight-law shots).
3. **Retain steps** leave no trace; their quotient goes on a stack of capacity one with the step index (12 + 7 qubits). A second
   retain step is a failure (measured: 0 of 300 shots with two).
4. The freeze bit `sh` of the template row stays (35 bits): without it a wrapped coefficient lands in `f[0]`.
5. **Row widths follow the locator degree.** At step `k` only `ceil((k+1)/2) + 1` coefficients of each row are touched. Measured on
   1,500 weight-law shots: the width actually needed exceeded `ceil((k+1)/2)` by exactly 1 in every shot.
6. Products use our rank-42 multiplier and the quotient and its recomputation use the tower inversion (`gfmul.py`, `tower.py`).

A bug found on the way: in the reverse pass the stack flag must be cleared before `c ^= 1 / (f[0] b)` is applied (otherwise `c != 0`
leaves the flag set): 50% phase errors with 0 value errors, because the measurement-based clears hide the unrestored registers.

Small fields cannot judge failure rates (q = 16 or 64 fail from ordinary degeneracy at the 1/q level); `mid12`, `narrow` and `full`
are the instances that count.

## Results

| version | qubits | Toffolis | check |
|---|---:|---:|---|
| mid12 (n = 20, GF(2^12)), first build, builtin products | 646 | 100,493 | PASS 4,096 shots |
| narrow (n = 70, full field, 71 positions), builtin products | 1,874 | 685,910 | PASS 2 x 25,600 shots, 0 value, 0 phase errors |
| narrow, rank-42 products and tower inversions (PR 116) | 1,867 | 438,448 | PASS 2 x 25,600 shots |
| narrow, step-bounded widths (PR 118) | 1,867 | 354,298 | PASS 2 x 25,600 shots |

Full-size prediction is `narrow + 4,024 x per-position` Toffolis (the Forney scan is 96 per position here), same qubits.

| full size, Kaggle official verifier, 102,400 shots per salt, kernel `qcc-dqi-gen` | qubits | Toffolis | worst-salt cost | ratio vs 2.4439e13 | salts |
|---|---:|---:|---:|---:|---|
| first build (PR 114, builtin products), sha256 `090fb7f7b7e6...` | 1,874 | 1,120,442 | 4.7593e12 | 5.13 | 5/5 PASS, 0 failures |
| rank-42 products, tower inversions, step-bounded widths (PRs 116, 118), sha256 `b72bd806f523...` | 1,867 | 740,602 | 3.1490e12 | **7.76** | 5/5 PASS, 0 failures |

Per-salt costs of the second run: 3.1316e12, 3.1490e12, 3.1316e12, 3.1316e12, 3.1122e12 (the static count matched the prediction to the Toffoli;
zero failures in 5 x 102,400 shots gives R = 1.19). Ledger rows are in `ledger/results.jsonl`; the circuits and logs were downloaded by us to
`out/kaggle/leejianrong__qcc-dqi-gen/` (gitignored). Best own DQI so far (Lanczos was 6.81); not promoted (`best/` needs 10 full salts through `bench promote`, and the public frontier is about 65).

## Where it stands and the next lever

Qubits 1,867 (Lanczos: 1,403), Toffolis 0.74M, R 1.19: ratio 7.76 against the previous best 6.81. The scan is 52% of the Toffolis (4,024 x 96). The reciprocal-polynomial scan of Gu et al. (23 Toffolis per position, `Psi sigma' = 1 mod sigma`,
`sigma = E^2 + z O^2` in characteristic 2, Euclid on the half-degree pair) would save about 290k Toffolis (ratio about 11 to 12). It
needs the Euclid in place in the 35 zero syndrome words (Omega in place leaves `S_35 .. S_69` zero) with a fixed schedule
and the quotients parked in cleared words; a second BM run on the series `O / E` was costed and loses (about +430 qubits for the rows).
That in-place Euclid is not built.
