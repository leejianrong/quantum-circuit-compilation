# dfthcsos: co-design the table and the loader (QCC-16, QCC-15)

Goal: beat the unary loader's ratio 6.85 ([dfthcsos-loader.md](dfthcsos-loader.md)) by fitting our own angle
table to a loader family that is cheap for it, instead of loading a generic table. Everything here is ours:
the loader is derived below from first principles (ADR-0009 stage 1), and the factorization starts from the
FCIDUMP with our own optimiser, not from any public table.

## Step 1: a loader whose cost is the rank of the table (E002)

`src/dfthcsos_gen/bilinear.py`. Split the address `a = h * L + l` with `L = 2^lb`. Build the one-hot lines of
`h` and of `l` once per circuit (about `H + L` Toffolis and qubits; for 1220 addresses `lb = 5` gives
`H = 39`, `L = 32`, 71 lines). Every output bit is then a plane `P[h, l]` of `H x L` bits:

- `F(h)` and `G(l)` are free (CNOTs from the set lines into the target bit).
- A rank-one term `alpha(h) beta(l)` is one Toffoli: CNOT the lines of `alpha` into one pivot line and those of
  `beta` into another, `CCX` into the target, undo.
- Two rank-one terms share one Toffoli, since `(alpha1 + beta2)(alpha2 + beta1)` expands to
  `alpha1 beta1 + alpha2 beta2` plus a pure-`h` and a pure-`l` part that `F` and `G` absorb.

So a plane costs `ceil(rank / 2)` Toffolis, `rank` being the GF(2) rank of `P` with row 0 and column 0 removed
by centering (`centered_rank`). A random plane has centered rank 31 (16 Toffolis, no better than unary
iteration); a plane of centered rank 10 costs 5. The cost of a whole table is therefore a function of its plane
ranks, which is exactly what a fit can steer.

First-principles count for the public geometry: 71 lines of qubits leave `128 - 11 - 71 = 46` qubits, so
`J = 5` words of 8 bits (K = 15). Per pass the cost is `15 * 70` for lines plus `600 * s` for the 600 planes
(`s` Toffolis per plane on average). The public circuits' 4,151 per pass is `s` of about 5.2, i.e. plane rank
about 10, which is the structure the earlier note inferred from gate statistics; here it follows from the
counting. Each unit of `s` is 1,200 Toffolis in `T_total` (8% of the score), so a lower rank budget is worth
exactly that much.

Tests (`tests/unit/test_dfthcsos_bilinear.py`): plans reproduce planes of every rank, the static count equals
kickmix's `num_toffoli_like`, and the circuit, simulated in kickmix, loads the table with no phase kickback and
clean workspace.

## Step 2: our own continuous factorization (E003)

`src/dfthcsos_gen/fit.py` is `error_2^2` and its gradients as Gram-matrix expressions on the symmetric-pair
space (gradients tested against finite differences; one evaluation about 2 s under load). Facts from the FCIDUMP
integrals plus shift `T`: `|T|_F = 12.18`, one eigenvalue is negative (-3e-4), and the best rank-`k`
approximation error is in the table below. A plain double factorization with
`R*C = 352` matrices already reaches 0.0074, so the THC structure (`X_rc` inside the span of `B` rank-one
matrices) has to fit inside the remaining 0.02 gate.

| k (rank of `T`) | 100 | 200 | 300 | 352 | 500 | 800 |
|---|---:|---:|---:|---:|---:|---:|
| tail error | 0.374 | 0.077 | 0.0167 | 0.0074 | 0.0013 | 0.0003 |

(Results of the fit follow below as they come in.)

## Results so far (E003, E004)

**E003, own continuous fit from scratch** (`scripts/run_fit.py`, shape (8, 143, 44), random unit vectors,
L-BFGS on `error_2^2`, 6 threads on a machine at load 40-80): `error_2` 0.446 (100 iterations), 0.219 (200),
0.153 (300), 0.122 (400), 0.091 (600), 0.083 (700), about 3 to 6 s per iteration. It is still descending, but
slowly; the gate is 0.02 and the public shape's reported floor is 0.0192, so a from-scratch fit needs many
thousand more iterations or a better initialisation (the DF eigenvectors are dense, so the fixed-target
decomposition per group is not a good start). No own table passes the gates yet, so no verifier run is
justified and the ledger is unchanged: best verified remains 489,890,973 (ratio 6.85) with the public words.

**E003b, the same fit on a 32-vCPU RunPod CPU pod** (`scripts/run_fit.py`, 90 minutes, about 1.5 USD; the
target `tsym.npy` was sent with `runpodctl send`, the code cloned from the public repo; four processes of
8 BLAS threads each). Pod speed was 0.7 s per iteration against 3 to 6 s on the laptop. `error_2` after
the 90 minutes:

| shape (R, B, C) | seed | iterations | `error_2` |
|---|---:|---:|---:|
| 8, 143, 44 | 0 | 7,300 | 0.0288 |
| 8, 143, 44 | 1 | 3,000 | 0.0414 |
| 8, 143, 44 | 2 | 2,950 | 0.0406 |
| 9, 127, 39 | 0 | 7,300 | 0.0329 |

Curve of the best run: 0.29 (150 it), 0.087 (650), 0.059 (1,250), 0.036 (3,550), 0.031 (5,900), 0.0288
(7,300). It is still descending but by about 0.0005 per 700 iterations at the end, so the gate (0.02) is
not reachable by simply running longer from this start; the public shape's reported floor is 0.0192 and
needs a better optimiser or a better initialisation. Seeds 1 and 2 ran 2.4x slower per iteration (the
processes competed for cores unevenly) and are behind at equal wall time, not necessarily at equal
iterations. The R=9 shape is no better.

Scored with the host's metric code (`scripts/eval_fit.py`; one-body rows are the exact eigenvectors of
`h1_prime`, so `error_1` is 1e-13; the capital `W_rho_c` is not fitted, only scanned along `W = -t sum_b w`):
`error_1` 0, `error_2` 0.0288 (fails the 0.02 gate), `Lambda` 745 and `E_gap` 12.6 Ha at the best `t` = 1.40
(minimum gap along this one-parameter family; the floors Lambda > 49.0 and E_gap > 3.914898 are met). The public
sample has `Lambda` 308 at `E_gap` 3.958, so fitting `W` properly is a second lever once `error_2` passes.
Fitted arrays stay in `out/` (not committed). No verifier run is justified; the ledger is unchanged.

**E004, rank-budget rounding on a stand-in table** (`src/dfthcsos_gen/rankfit.py`). To develop the rounding code
before our own table exists, the host's 12-bit baseline angles (Apache-2.0 sample submission, development only,
never an output) are read as continuous 8-bit angles. Findings:

- Nearest-rounded bit planes of 3,976 rows have centered GF(2) rank 61 to 62 for bits 0 to 5 and 36 to 37 for
  bits 6 and 7: no plane is low rank by accident, and the sign-like top planes are not either.
- Forcing every plane to rank 8 after the fact (soft-decision alternating decoding, flip cost = increase of
  squared angle error) multiplies the angle mean-square error by about 14,000, almost all of it from the top
  planes where a flip costs up to 128^2. A rank budget cannot be imposed on rounded words.

Consequence for the design: the structure has to live in the factorization (parametrise the planes as
`F + G + rank-r` and optimise those discrete parameters, or choose the Givens tree and the address order so
that the high planes are smooth), which is the work the public authors must have done during training. That is
the next lever; the loader (E002) and the objective are ready for it.

Cost model, for reference: with the 2-D loader at `J = 5` the angle cost per pass is `15 * 70 + 600 s`, so
`s = 5.2` reproduces the public 8,302 (ratio 11.2) and every unit of `s` below that is worth 8% of the score;
a plain unary loader at `J = 13` is 6.85.
