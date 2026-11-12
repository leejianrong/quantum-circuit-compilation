# dfthcsos: our own table passes the gates (M1) and the road to the frontier (QCC-16, QCC-15)

Everything here is ours (ADR-0007, ADR-0009): the table is fitted from the FCIDUMP with our own optimiser, the
loader is our unary iteration, the post-processing is written from the verifier's decoding rule. No public
circuit, word table, gate list or constant was read for this work, so nothing was added to the "Ideas learned"
list in `docs/PROVENANCE.md`.

## Result

**M1 reached.** An own factorization of shape (R, B, C) = (8, 176, 56), encoded at 12 bits on a balanced Givens
tree and loaded by our unary loader (J = 8, 10 circuits, 117 qubits), passes the real verifier at 3 of 3 salts:

| | value |
|---|---|
| verifier cost | 1,850,153,217 (ratio 1.81 against the 3.3556e9 baseline) |
| `error_1`, `error_2` | 0.0036, 0.0165 (gates 0.02) |
| `Lambda`, `E_gap` | 480.4, 4.0906 (floors 49.0 and 3.914898) |
| `lambda_eff` | 62.56 (public refit 46.9) |
| cost model prediction | 1,850,153,217 (exact, from the stats of the circuits) |

The whole circuit is ours, with no public words. It is not a promotion candidate: the best verified dfthcsos is
still 489,890,973 (ratio 6.85, public table). The gap to 6.85 is bit width and `lambda_eff`: at 12 bits the angle
Toffolis are 29,640 (J = 8, K = 10) against 14,616 at 8 bits, and `Q_total` is 789 against 491 because the inner
QROAM block exponent follows `75 * brot`; `lambda_eff` 62.6 against 46.9 costs another 1.33x.

## What worked in the fit (E005 to E007)

Setup as in [dfthcsos-codesign.md](dfthcsos-codesign.md): `error_2^2` with hand gradients, L-BFGS, 32-vCPU RunPod
CPU pod (spot, 0.96 USD/h, three pods, about 3.4 USD in all; one pod was lost for 20 minutes to a relay sender
that died, nothing else). Our own `tsym.npy` was sent with `runpodctl send` and deleted with the pod.

**E005, shape study from a random start, 93 minutes, four processes** (`scripts/run_fit.py`):

| shape (R, B, C) | maxcor | iterations | `error_2` |
|---|---:|---:|---:|
| 8, 143, 60 | 20 | 8,800 | 0.02147 |
| 8, 143, 52 | 20 | 8,900 | 0.02412 |
| 8, 176, 44 | 20 | 8,300 | 0.02248 |
| 8, 143, 44 | 100 | 7,100 | 0.02698 |

Same iteration count as the earlier 0.0288 run (E003b) but 0.0215 to 0.027: this time the runs were not stopped
by the clock. Larger C and larger B both help; a bigger L-BFGS memory (maxcor 100) is slower per iteration and
no better. At equal iterations C = 60 beats C = 52 beats C = 44.

**E006, continuation by growth** (`--init-from`): pad a converged fit with new `c` columns or new `b` rows that
start at 5% of the typical weight (a zero start has zero gradient, so it must be nonzero) and keep optimising.
84 minutes:

| start | grown to | iterations | `error_2` |
|---|---|---:|---:|
| 8,143,60 (0.0215) | 8,143,72 | 8,500 | 0.0157 |
| 8,143,60 (0.0215) | 8,143,60 (plain continue) | 8,800 | 0.0176 |
| 8,143,60 (0.0215) | 8,176,60 | 7,800 | 0.0163 |
| 8,176,44 (0.0225) | 8,176,56 | 7,800 | 0.0138 |

Growing is the lever: it crosses the plateau that more iterations alone do not (plain continuation gained 0.004,
growth 0.006 to 0.009). The best table is the 8,176,56 one at 0.0138, well inside the gate.

## What is needed on top of a continuous fit (E007)

1. **Rotation of the `c` index** (`dfthcsos_gen.post.rotate_min_l1`). `sum_c X_c (x) X_c` is invariant when `w[rho]`
   is multiplied by an orthogonal matrix on `c`, so `error_2` does not move, but the column one-norms do:
   a smooth-L1 Riemannian descent halves `sum_c |w_c|_1^2` (for example 223.6 to 104.5 for one rho). This is worth
   a factor of about 1.5 in `Lambda`. A real L1 term inside the fit would probably do more; not tried.
2. **Capital `W`** (`scripts/dfthcsos_post.py`, `fit_cap_w`): 352 to 448 free parameters, objective `lambda_eff`,
   constraint `E_gap >= floor + 2e-4`, analytic gradients through the eigenvalues of `h1_prime`, SLSQP. Every
   starting point (`W = -t sum_b w`, t = 0.5 to 2) lands on the same optimum, so the problem looks convex enough.
   Result `lambda_eff` 61.7 to 62.6 against 136 for the one-parameter scan in E003b. The stored array is
   `H2_I = W + sum_b w` (the verifier subtracts `sum_b w`), in float32, and the script evaluates with the rounded values.
3. **Bit width.** The verifier scores the decoded words, so quantization adds to `error_2`. Tree matters: on the
   same fit (error 0.0215) the balanced heap tree gives 0.0555 at 10 bits and 0.0255 at 12, the path tree 0.1207 and 0.0370.
   Refitting `w` on the decoded vectors (quantization-aware weights) removes about a tenth of the loss
   (0.0555 to 0.0419 at 10 bits, 0.0255 to 0.0236 at 12). One-body rows are the eigenvectors of the decoded
   `h1_prime`; their `error_1` scales as `2^-brot` (0.014 at 10 bits, 0.0035 at 12).

## Cost of the passing table and what it says about M2

The cost model gives `T_total` = 29,640 + 4,393 + 3,450 and `Q_total` = 789 at 12 bits. To get back to 6.85 the table
has to live at 8 bits (J = 13, K = 6, Q = 491) and `lambda_eff` has to come down to about 47. Both are fit
problems, not loader problems: a continuous fit at 0.0138 has 0.006 of slack under the gate, and an 8-bit grid
costs about 0.05 of `error_2` when rounded naively, so the optimiser has to be told about the grid.

## Not done

M2, the structured fit with the bilinear loader (planes parametrised as F + G + rank-r), was not started. The
budget went into getting a table that passes at all and into the bit-width problem, which is the larger factor
between 1.81 and 6.85.
