# dfthcsos: can our own table reach 8 bits? (QCC-16, QCC-15, E021)

Question from [dfthcsos-structured.md](dfthcsos-structured.md): the cost model says the fully-own ratio 1.98 (11 bits)
jumps to about 4 at 8 bits (Q_total 790 to 494), so is there a gentler end to the quantisation schedule, or a fit,
that gets `error_2 < 0.02` on an 8-bit grid? Everything here is ours (ADR-0007, ADR-0009). Setup: laptop, our
own (8,143,44) fit from the pod (`error_2` 0.0288, `fits/seed_8x143x44/`), `tsym.npy` from the FCIDUMP, balanced
tree. The 0.0138 (8,176,56) table and the 11-bit words of the previous session were not kept (only `out/` of a deleted
worktree), so every number below is on the weaker 0.0288 seed; compare rows with each other, not with E020.

## Result: negative at 8 bits, and the "gentle end" is not the problem

| experiment | bits | `error_2` | note |
|---|---:|---:|---|
| naive rounding of the seed | 8 | 0.2105 | continuous 0.0288 |
| naive rounding of the seed | 10 | 0.0607 | |
| E008 schedule (`dfthcsos_qat.py`, 6 stages x 80 it) | 8 | above 0.09 (stopped) | 40% frozen: 0.062, 65%: 0.092, 80%: 0.090, continuous 0.052 |
| same schedule | 10 | 0.0383 | |
| 66 stages, nearest-to-grid order, 30 it each (`dfthcsos_qat2.py --order nearest`) | 10 | 0.0380 | finer end: no gain |
| 24 stages, floor/ceil chosen by the quadratic model (`dfthcsos_qat2.py`) | 10 | 0.0423 | worse |
| 66 stages, same model order | 10 | about 0.042 | worse |
| noise-robust fit (`dfthcsos_noisefit.py`, mean of `error_2^2` over 2 rounding-noise draws, ramp 0.1 to 1) | 8 | 0.159 after final rounding (expected 0.15) | naive 0.21: a quarter off, 8x short |
| lattice descent (`dfthcsos_lattice.py`, single +-1 word moves ranked by `g d + h d^2 / 2`) | 10 | no move set lowers it | 107 moves already add 0.02 |

Reading:

- At 10 bits the loss above the continuous fit is `sqrt(0.038^2 - 0.0288^2)` = 0.025 whatever the schedule. The
  previous session saw the same at 0.0138 (0.0216). The noise part falls about 2.3x against naive rounding and no
  further; a finer end (66 stages) changes it by 1%. Fixing 40% of the angles at 8 bits already costs 0.03, so
  the loss is not concentrated in the last angles at this width, it accumulates.
- Naive 8-bit noise is 0.206 (4x the 10-bit 0.051), so QAT would have to cut it 14x to leave room under the
  gate with a 0.0138 base. 2.3x is what every variant here delivers.
- Choosing floor or ceil by a quadratic model (gradient plus a Hutchinson diagonal Hessian) is worse than
  nearest rounding: the diagonal is dominated by off-diagonal noise (6 probes), the per-edge average is too
  coarse (curvature differs 600x between vectors, `g` and `h` checked against finite differences), and single moves
  are strongly coupled, so the predicted gains are not real.
- Noise-averaged fitting does not find a flat table in 100 L-BFGS iterations per ramp step; the expected error
  grows as the noise scale (0.033 at 0.1 to 0.15 at 1.0).
- Tree: our mean-field model (rounding energy of an angle = remaining mass at its parent) gives about `n log2 n`
  for any tree on near-uniform masses (mass entropy 6.21 of 6.25 bits), and a path or a mass-sorted tree is
  not better. The public table's tree is binomial (parent = index with the lowest set bit cleared, mean depth
  2.95), so depth is not what makes its 8 bits work; logged in `docs/PROVENANCE.md` as analysis only.

So the public (8,143,44) table at 8 bits and 0.02 is not reachable by rounding a continuous fit, even a good one
with compensation. What is missing is either a base error far below ours (our 0.0288 vs 0.0138 for 8,176,56,
and presumably lower for the public fit) or a fit done on the grid from the start with a discrete optimiser better
than coordinate-wise rounding. Neither is a small change.

## L1 term for `lambda_eff` (lever 2)

`run_fit.py --l1 mu` adds `mu * sum_(rho,c) |w_c|_1^2 / 4` (the `Lambda_2` term, smooth |w|) to the fit;
`dfthcsos_l1_eval.py` reports the proxy after the min-L1 `c` rotation (Lambda_1 and the W term left out). 400
iterations from the seed:

| `mu` | `error_2` | proxy before rotation | proxy after rotation |
|---:|---:|---:|---:|
| 0 | 0.02848 | 510.6 | 285.4 |
| 1e-6 | 0.02868 | 470.8 | 271.5 |
| 4e-6 | 0.03063 | 387.3 | 247.3 |

The trade is poor: 13% off `Lambda` (7% off `lambda_eff`) costs 7% of `error_2`, which the 11-bit table cannot
spare (E020 sits at 0.0179 of 0.02). Longer fits may do better; not tried. The public `lambda_eff` 46.9 needs
`Lambda` 283 against our 482, and the rotated proxy of our own seed is already 285, so the rest is the
capital-W and one-body terms plus quantisation, which is the next thing to look at.

## Shape search (lever 4), cost model only

Unary loader family, `lambda_eff` 62.6, ratio against 3.3556e9 (`dfthcsos_model`, same code path as E019/E020):

| (R, B, C) | 8 bits | 9 | 10 | 11 |
|---|---:|---:|---:|---:|
| 8,176,56 | 4.05 | 2.44 | 2.18 | 1.98 |
| 8,143,44 | 5.13 | 2.97 | 2.65 | 2.39 |
| 8,128,40 | 3.81 | 3.38 | 3.01 | 2.73 |
| 8,112,36 | 4.29 | 3.76 | 3.39 | 3.07 |
| 6,176,56 | 5.17 | 3.09 | 2.77 | 2.51 |

`A = 76 + R B` sets the loader (`2 K (A - 2)` Toffolis) and the inner-QROAM block exponent; the 8-bit Q cliff exists
only for B above 128 (shapes with `b2 = 18` stay at Q about 760). So at 10 to 11 bits a smaller shape is worth up
to 1.5x, if its continuous fit reaches the gate: this is a fit-quality question again (0.0288 at 8,143,44 after 7,300
iterations against 0.0138 at 8,176,56).

## Running on Kaggle (free CPU, no pod)

`notebooks/dfthcsos_fit/` (a private script kernel, `competition_sources` for the FCIDUMP, `pip install kickmix`, a clone
of the public repo, a 4-core session) rebuilds `tsym.npy`, runs the jobs in `JOBS`, streams a log and checkpoints
`fit/<run>/` every 100 iterations; attach a finished kernel through `kernel_sources` to continue it.

| kernel | job | purpose |
|---|---|---|
| `leejianrong/qcc-dfthcsos-fit` | seed (8,143,44) grown to (8,176,56), 9,000 iterations (about 4 h) | recover the 0.0138 table that the previous session lost |
| `leejianrong/qcc-dfthcsos-fit-b` | (8,143,44) continued 30,000 iterations (about 10 h) | how low the small shape goes with a long run (shape search) |

Fetch with `uv run bench kaggle fetch leejianrong/qcc-dfthcsos-fit` (and `-b`); outputs land in `out/kaggle/`.

## Next

1. Fetch both fits. If (8,143,44) reaches about 0.015 or better, QAT at 10 and 11 bits on it gives ratio 2.65 and 2.39 with our
   loader, the cheapest verified gain left (lever 4); if not, the 8,176,56 table redone at 11 bits reproduces 1.98.
2. 8 bits needs a different optimiser (discrete, joint in angles and weights), not a better schedule; budget it
   only after item 1.
3. Past 2.4 the loader is the cost (78% of `T_total` at 11 bits): the structured bilinear loader with a table
   fitted to a rank budget (`bilinear.py`), not started.
