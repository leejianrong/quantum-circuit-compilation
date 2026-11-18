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

## Stage 2: the `Lambda`-penalised fit (2026-11-18, GPU)

`scripts/run_fit_gpu.py --mu MU` adds `MU * 1/4 sum_(rho c) (sum_b |w_bc|)^2` (smooth abs, `penalty()`) to the `error_2^2`
objective, starting from fit-c (8,176,56), 40 minutes of L-BFGS per value on the RTX 3080 Ti (about 9,300 iterations
each, torch 2.9.1+cu128 in `~/qcc-gpu-venv2`; torch 2.15+cu132 segfaults on CUDA init here). Each result goes
through the same post-processing as before (`dfthcsos_post.py --brot 16 --rotate-restarts 4 --joint-rotate 3`) so the
numbers are comparable. All [M]; the logs of the six runs are in `~/qcc-fits/own/pen_mu*/log.jsonl`.

| fit | `error_2` | `Lambda` | `lambda_eff` | vs fit-c |
|---|---:|---:|---:|---:|
| fit-c, pipeline gauge (stage 0) | 0.01474 | 488.6 | 63.05 | |
| fit-c, restarts + joint rotation (stage 1) | 0.01474 | 416.8 | 58.21 | -7.7% |
| penalised, mu = 1e-7 | 0.01262 | 354.3 | 53.63 | -14.9% |
| mu = 3e-7 | 0.01276 | 336.3 | 52.25 | -17.1% |
| mu = 1e-6 | 0.01308 | 315.4 | 50.60 | -19.7% |
| mu = 3e-6 | 0.01379 | 298.6 | 49.22 | -21.9% |
| mu = 1e-5 | 0.01452 | 286.6 | 48.24 | -23.5% |
| **mu = 3e-5** | 0.01484 | **283.6** | **48.06** | **-23.8%** |
| public v13 table | 0.0200 | 283.3 | 46.93 | |

Findings:

1. **The basin hypothesis holds and a penalised fit reaches it.** `Lambda` falls monotonically with `mu` and saturates at
   283.6, equal to the public 283.3, at `error_2` 0.0148, still inside the 0.02 gate. Kill criterion (above 400 after three
   restarts) clearly not met: the unpenalised fit's 490 to 560 was a different basin that no amount of fitting or gauge
   work reaches, and a penalty from the first iteration does.
2. The penalty also lowered `error_2` at small `mu` (0.0147 to 0.0126 at 1e-7): the penalised objective escapes a worse
   basin on both counts. At larger `mu` error rises slowly, so `mu` of 1e-5 to 3e-5 is the useful range here.
3. The remaining `lambda_eff` gap to the public table (48.06 against 46.93, 2.4%) is `E_gap`: ours sits at 4.102 and
   the public table at the floor 3.9149; `lambda_eff = sqrt(E_gap (2 Lambda - E_gap))`. The capital-`W` fit trades them;
   a joint rotation round no longer helps at `mu` = 3e-5 (the penalty has already used the gauge).
4. Effect on the score if these words could be rounded to 11 bits as E040 was: `lambda_eff` 63.14 to 48.06 is 1.31x,
   so E040's 2.50 would be about 3.3. The words and loader factors of S2 (bits, planes) are the rest of the gap.

Process notes: a queued job that read `scripts/run_fit_gpu.py` from the working tree broke when I switched branches (the
first `mu` ran on code loaded earlier and is valid); later jobs ran from a copy outside the repository. The final sweep job
was killed at the end of `mu` = 3e-5 by a session teardown (checkpoint at iteration 8,800 of about 9,500, `error_2`
0.01482); the number above is from that checkpoint.

## Stage 3: bits (2026-11-19)

`dfthcsos_qat.py --half` (error-only quantisation-aware fit, no penalty) on the `mu` = 3e-5 fit:

| bits | final all-rounded `error_2` | gate 0.02 |
|---|---:|---|
| 8 | 0.0994 | fails |
| 10 | 0.0299 | fails |
| 11 | 0.01883 | passes |

Plain rounding at 11 bits (300 weight-refit iterations, no QAT) gives 0.0227 and fails narrowly. Same pattern as every earlier
fit (8 bits about 0.085, 10 bits 0.027, 11 bits passes): the penalty changes `Lambda`, not the bit requirement, and 8 bits
still needs a rounding method we do not have.

At 11 bits the full pipeline (`dfthcsos_post.py --brot 11 --half --loader anf --rotate-restarts 4 --joint-rotate 2`)
gives: `error_1` 0.00698, `error_2` 0.01883, `Lambda` 284.9, `E_gap` 4.0867, `lambda_eff` 48.09 (E040: 63.14); best loader
`lb = 6`, J = 3, 10,875 Toffolis, 120 qubits; predicted cost 1,022,615,598.

**Official verifier, 3 salts, 0 failures: cost 1,022,615,598.11, ratio 3.28** [M] (ledger row `09324acd`, 47 s wall; the model
predicted it to all printed digits). Our own best for dfthcsos goes from 2.50 (E040) to 3.28, a factor 1.31 = 63.14 / 48.09 as predicted.
Circuit directory `~/qcc-circuits/own_dfthcsos_11bit_pen` (outside git; regenerate with the commands above from
`~/qcc-fits/own/pen_mu3e-5`). It is far below the public 11.38x and not a promotion candidate.

## Where the rest of the gap is

3.28 against 11.38 is 3.47x. `lambda_eff` is now within 2.4% of the public table, so the remaining factor is `T_total * Q_total`:
our 11-bit loader costs 10,875 Toffolis and 120 qubits per pass against the public table's 8-bit words and its own loaders
(about 14,700 Toffolis and 427 total qubits for the whole benchmark, S2). Closing it needs 8-bit words that pass the gate
(the public table's rounding polish) and the public loader structure (QCC-69).
