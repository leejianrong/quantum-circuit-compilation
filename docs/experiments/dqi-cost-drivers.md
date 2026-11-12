# DQI: where the host reference spends its cost (QCC-17)

Audit of `data/verifiers/dqi/dqi_reference_circuit.py` and `verify_submission_dqi.py` (both Apache-2.0,
read only). Tool: `src/dqi_gen/audit.py` (per-`mark` Toffoli tally, checked against kickmix's own
`operation_statistics()` total). Full-size numbers are extrapolated from measured instances because the
full circuit does not fit this 7 GB laptop (ADR-0002). The exact full-size tally was then run on Kaggle
(`notebooks/dqi_gen`, 71 s, 8.9 GB peak) and matches the extrapolation: see the exact table below.

## The cost formula, as the verifier computes it

`score = R(eps_plus) * Q^2 * T`

- `Q = circuit.num_qubits`: **every** qubit, the 840 syndrome qubits included. It is squared, so one
  qubit saved is worth two Toffolis' worth of relative cost: a 1% cut in Q equals a 2% cut in T.
  This confirms the public claim that "qubits are counted twice".
- `T` = mean over the 102,400 shots of Toffoli-like gates (`CCX`, `CCZ`, `CSWAP`) that actually
  execute in that shot (`sim.operation_statistics()`), not the static count. Only `PUSH_CONDITION` blocks
  on classical bits can skip work. The reference wraps each Forney position in a condition on "this
  position's `M_j` is non-zero", which is true with probability 1 - 2^-12, so executed T is within 0.1% of
  static T (63x6 instance: 93,542.9 vs 93,623). Conditioning on a quantum value (for example "sigma has a
  root here") is impossible, so there is no data-dependent saving to harvest at this level.
- Decoder failures: a shot fails if any syndrome or ancilla qubit differs at the end (`value_errors`) or the
  phase is wrong while those are fine (`phase_errors`). With `k` failures in `N = 102,400` the
  one-sided Clopper-Pearson upper bound `eps_plus` at confidence `1 - 2^-128` must stay below 1/16, and
  `R(eps) = ln 2 / -ln(1/2 + 2 sqrt(eps))`. Zero failures give `eps_plus = 8.7e-4` and `R = 1.19` for every
  exact circuit (the floor). Each extra failure raises `eps_plus` by roughly 1.4e-4 at first. Examples:
  `R(1e-3) = 1.21`, `R(1e-2) = 1.94`. Approximation only pays if it removes more than `1 - 1/R` of the cost.
- Small instances: with fewer than about 1,400 shots the zero-failure bound is already above 1/16 and the
  verifier raises. Use at least 2,048 shots (`bench`-style small runs in QCC-18).

## Stage breakdown of the reference

Measured per-stage Toffolis (static), reference builder, GF(2^12) unless noted:

| instance (m, n, b) | qubits | total | forward EEA | reverse EEA | Chien+Forney | shifts (2x) |
|---|---:|---:|---:|---:|---:|---:|
| 63, 10, 6 | 229 | 93,623 | 43,690 | 43,690 | 5,415 | 828 |
| 255, 20, 8 | 462 | 326,692 | 144,056 | 144,056 | 34,780 | 3,800 |
| 511, 30, 9 | 699 | 784,376 | 346,722 | 346,722 | 81,768 | 9,164 |
| 21, 20, 12 | 682 | 544,563 | 265,020 | 265,020 | 9,051 | 5,472 |
| 31, 30, 12 | 927 | 1,017,249 | 495,842 | 495,842 | 13,617 | 11,948 |
| 41, 40, 12 | 1,168 | 1,628,131 | 794,576 | 794,576 | 18,231 | 20,748 |
| 51, 50, 12 | 1,408 | 2,376,205 | 1,160,850 | 1,160,850 | 22,557 | 31,948 |

For fixed degree 12 the EEA pass fits `337.7 n^2 + 6,234 n + 4,892` (checked to 1% on the four points), so
at `n = 70`: about 2.10M per pass. Chien+Forney is exactly 351 per position (the paper's Itoh-Tsujii
figure), `4095 x 351 = 1,437,345`. Exact full-size tally (Kaggle, 5,725,461 Toffolis, 1,893 qubits, equal to the paper's figures); our
extrapolation above gave 2.10M per EEA pass and 1.437M for Chien+Forney:

| stage | Toffolis | share |
|---|---:|---:|
| forward EEA | 2,109,450 | 36.8% |
| reverse EEA | 2,109,450 | 36.8% |
| Chien search + Forney + MBUC phase | 1,444,737 | 25.2% |
| initial shift and its inverse | 30,912 + 30,912 | 1.1% |
| total | 5,725,461 | |

Qubits at full size: 1,893 = 840 syndromes + 1,053 workspace (2 arrays of `n + 3 = 73` registers of 12
qubits minus the 3 reused syndrome registers, five pointers, the 48-qubit inversion scaffold, flags).

Inside one EEA pass (instance 511, 30, 9, inclusive shares of the whole circuit): multiply-and-subtract
64% (the unary-iteration `sweep_positions` alone 54%, a 4-way `unary_iteration` over the pointers per
position), quotient division 9%, `shift_b_array_right` 10%, `swap_a_and_b` 8%, flag update 3%. Field
inversion (`gf_inverse_chain`) is 15% of the circuit at this size, almost all of it the Forney sweep.

## What this says about the public findings

- "Berlekamp-Massey / Schur style beats Euclid": the key-equation stage is 73% of the reference. Our own
  divstep solver (QCC-19, `docs/experiments/dqi-divstep-v0.md`) does the same job in about 0.93M Toffolis
  (forward 0.52M plus reverse 0.40M), 4.6x cheaper, so the claim holds for Toffolis. It costs more qubits
  in our first version, which matters because of `Q^2`.
- "Forney sweep is 56% of Toffolis in the best public design": plausible, since it is a fixed 1.44M in the
  reference and does not shrink with a better solver. With a divstep solver at 0.93M it is already 61% of
  our total. The sweep cost is `m x (one inversion)`, so the lever is the per-position inversion
  (351 Toffolis) and how many field multiplications it needs.
- "Qubits counted twice": verified above (`Q^2`).

## Next levers, in order

1. Qubits. The public frontier (about 892 qubits, i.e. 840 plus about 52) must keep the key-equation state
   in or beside the syndrome registers; `S <-> (sigma, Omega)` is a bijection on decodable syndromes. Q enters squared.
2. Per-position inversion in the Forney sweep (351 Toffolis, 4095 times).
3. The solver (already 4.6x cheaper than Euclid in our version).

Reproduce: `QCC_DATA=data uv run python -m dqi_gen.audit --m 63 --n 10 --degree 6` (seconds).
