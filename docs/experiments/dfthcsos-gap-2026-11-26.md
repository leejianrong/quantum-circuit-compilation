# dfthcsos: where the 4x gap to the public package sits, and the iteration loop (QCC-16)

Question: our best own dfthcsos is 3.28x (`09324acd`), `best/` holds 13.36x (`24516e97`, ozertuu 25-218 package). Which
verifier terms make up the 4.07x, so that the next hour goes to the largest one? All numbers [M]: the official verifier
(`data/verifiers/dfthcsos/verify.py <dir> --salt x`), one salt each, on 2026-11-26.

## Measured breakdown

| | public `24516e97` | ours `09324acd` | ratio |
|---|---:|---:|---:|
| score | 251,089,557.5 | 1,022,615,598.1 | 4.07 |
| `brot` (bits per word) | 7 | 11 | |
| shape (R, B, C); addresses A = 76 + R B | (9, 127, 46); 1,219 | (8, 176, 56); 1,484 | |
| loaders (circuits), words per circuit | 15, 5 | 25, 3 | |
| `lambda_eff` (`Lambda`, `E_gap`) | 46.918 (283.10, 3.9149) | 48.085 (284.94, 4.0867) | 1.025 |
| angles Toffoli, both passes | 6,714 (3,357 per pass, about 224 per circuit) | 21,750 (435 per circuit) | 3.24 |
| inner state-prep Toffoli / outer | 4,213 / 337 | 4,033 / 360 | |
| Givens Toffoli | 1,950 | 3,150 | 1.62 |
| `T_total` | 13,214 | 29,293 | 2.22 |
| inner prep temporary qubits | 287 | 607 | 2.1 |
| `Q_total` | 405 | 726 | 1.79 |
| angles circuit qubits (cap 128) | 128 | 120 | |

What follows from it:

1. `lambda_eff` is not the gap any more (S4 stage 2 closed it). `T_total` 2.22x times `Q_total` 1.79x is the whole 4.07x.
2. Almost all of both is `brot`. The Givens cost is 75 (4 `brot` - 2) Toffolis (42 per angle at 11 bits, 26 at 7). The loader count is
   the 75 columns times `brot` over about 34 output bits per circuit (15 at 7 bits, 25 at 11). The inner-prep workspace is the QROAM
   size, which follows `brot` and the number of words. The public table's words are genuine 7-bit values (0 to 127, 1,219 rows), not
   8-bit words with a free bit.
3. Per circuit the public loader is about 1.9x cheaper than ours at the same output width (224 against 435 Toffolis). That is a second,
   independent lever (loader structure; the reading is in `dfthcsos-syed-decode.md`, matroid planner `src/dfthcsos_gen/matroid.py`).
4. The shape differs too (A 1,219 against 1,484: 18% fewer words), so a smaller factorization is the third lever (QCC-16).

Earlier notes ruled 7 bits out on the (8, 143, 44) table (`dfthcsos-low-brot.md`: our 7-bit design fails `error_2` by 8.8x, a passing
one worth about 3% on that shape). That reasoning is superseded: a 7-bit table at a different shape passes at `error_2` 0.0200 and is
worth 2.2x on T and 1.8x on Q here. The exchange rate that note used ignored that `brot` scales loaders and Givens together.

## Iteration loop

| Step | Tool | Time | Gate? |
|---|---|---|---|
| change `brot`, shape, words | `scripts/dfthcsos_qat.py`, `dfthcsos_post.py` (CPU, 6 to 10 min per bit width); GPU fits via pueue only if the GPU is free | minutes | no |
| predict cost and gates | `dfthcsos_model.score` plus the verifier's `evaluate_words` (about 3 s, no circuits) | seconds | no |
| build circuits | `dfthcsos_post.py --loader anf` | about 1 min | no |
| official check, 1 salt | `bench verify dfthcsos <dir> --salts 1` | 45 to 150 s | row is evidence, not for promotion |
| official check, 10 salts | `flock /tmp/qcc-heavy.lock ... --salts 10` | 2 to 3 min | yes |
| promote | `bench promote --dry-run`, then for real | seconds | the only way into `best/` |

The model predicted the verifier to all printed digits for E040 and `09324acd`, so the loop never needs more than one official run per
candidate before the 10-salt run. invsqrt has no cheaper screen than the official verifier (2 to 5 minutes per salt); DQI goes through
`bench kaggle run notebooks/dqi_verify` only.

## Ranking by expected gain per hour

| Target | Gap | Loop time | Why |
|---|---:|---|---|
| dfthcsos, 7-bit words on a smaller shape (QCC-16, QCC-55) | 4.07x | minutes | largest gap, cost model exact, verify in minutes |
| dfthcsos, loader at 224 Toffolis per circuit (QCC-69 reading only) | 1.9x on angles | minutes | independent of the words |
| DQI (QCC-19, QCC-63) | about 1.19x to `best/` | 20 min on Kaggle | small gap, slow loop |
| invsqrt (QCC-61) | 2.8x | 2 to 5 min per salt | parked without a new idea |

Pick: dfthcsos. A 4x on one benchmark is 1.6x on the geometric mean; the leaders are 1.04x above us.
