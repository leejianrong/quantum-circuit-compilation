# S4: dfthcsos `Lambda` (QCC-62)

Hypothesis: our `Lambda` of 490 to 560 against the public 283 is a basin or gauge problem that a penalised fit or a
better gauge removes. Kill criterion: `Lambda` still above 400 after three restarts at matched `error_2`.

## Stage 1: what `Lambda` is made of (2026-11-17)

From the verifier source, `Lambda = sum_j |lambda_j| + 1/4 sum_(rho c) (||w_c||_1 + |W_c + sum_b w_bc|)^2`, where
`lambda_j` are the eigenvalues of `h1'` and `w` (R,B,C), `W` (R,C) are stored real arrays, not loaded by the circuits.
Only the vectors `u_b^rho` go through the circuits. [V]

| | one-body `sum |lambda_j|` | weight part | `Lambda` | `lambda_eff` |
|---|---:|---:|---:|---:|
| public v13 table (8,143,44), decoded words | 13.5 | 269.8 | 283.3 | 46.93 |
| our fit-c (8,176,56), continuous, pipeline gauge | 13.0 | 475.6 | 488.6 | 63.05 |
| fit-c, `--rotate-restarts 4 --joint-rotate 3` (end to end) | 13.0 | 403.8 | 416.8 | 58.21 |

[M] for all rows (verifier code on the decoded public words; our fit through `scripts/dfthcsos_post.py`, `--brot 16 --refit-iters 0`).

Findings:

1. The one-body part is not the gap. On the pipeline's rotated weights the capital-`W` fit reaches 13.0 from every start (t = 0, 0.7, 1, 1.3, 3,000
   iterations all give the same optimum; a warm start from the rotated `W` also gives the same value), as small as the public 13.5. The whole gap is the weight part.
2. The weight part depends on a gauge. `sum_c X_c (x) X_c` and `sum_c W_c X_c` are invariant under an orthogonal
   rotation of the copy index `c` applied to `w` and `W` together, so the rotation costs no Toffoli and no error.
   The pipeline's rotation (`post.rotate_min_l1`) minimises only the column one-norms from one start and ignores the
   `|W_c + sum_b w_bc|` term. Five random restarts with 1,500 iterations lower the L1 part by 17% (292.5 to 243.4),
   and a joint rotation that includes `W`, alternated with the `W` refit, takes `Lambda` from 488.6 to 416.8 (-14.7%) and
   `lambda_eff` from 63.05 to 58.21 (-7.7%). Implemented as `post.rotate_joint`, `dfthcsos_post.py --joint-rotate N`.
3. That closes about 30% of the distance to the public `lambda_eff` (63.05 to 46.93). The rest is the weights
   themselves: our mean column one-norm after rotation is about 1.6 against the public 1.17 per column, and the
   weight part grows with it squared. A different, sparser basin, not a gauge, is what is left.

Consequence: a joint-rotation `lambda_eff` gain of 7.6% would take E040 from 2.50 to about 2.7, a real but small
gain. By S2 the words gap (2.74x) is half `Lambda` (1.32 to 1.41) and half bits and planes, so no `Lambda` work alone
closes dfthcsos.

## Next stages

2. Penalised fit from the start: add `mu * 1/4 sum (||w_c||_1 + |W_c + sum_b w_bc|)^2` to the `error_2^2` objective in
   `scripts/run_fit_gpu.py` and sweep `mu` to the `error_2` = 0.02 gate. This is the real test of the basin
   hypothesis and needs the GPU queue (pueue); the GPU is in use by another session until about 04:00.
3. Then 8-bit rounding of the penalised fit (needed for the other half of the gap).

## Lesson

A flag that was parsed but never passed to `build()` made the first end-to-end run show no effect from the restarts (61.40 against the scratch 58.25). The cross-check against an independent scratch run caught it; check that a new option changes the output before trusting a null result.
