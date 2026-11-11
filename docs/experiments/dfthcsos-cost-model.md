# dfthcsos cost model (QCC-14)

`src/dfthcsos_model/` reproduces the verifier's score without running it. Tests in
`tests/unit/test_dfthcsos_model.py` pin it to numbers recorded from real verifier runs.

## What the model takes

```python
from dfthcsos_model import Angles, score

b = score((R, B, C), Angles(toffoli=..., qubits=..., J=..., brot=...), Lambda, E_gap)
b.score, b.t_total, b.q_total, b.q_temp_source
```

- `(R, B, C)`: the factorization shape. It sets the state-preparation Toffolis and qubits.
- `Angles`: the loader family as the verifier reads it: `toffoli` (twice the sum of each circuit's
  static `num_toffoli_like`, which equals the simulator's per-shot mean when no Toffoli is
  conditioned on a measurement), `qubits` (max over circuits), `J` words per circuit, `brot` bits per word.
- `Lambda`, `E_gap`: the accuracy metrics of the loaded words. They need the integrals and the
  decoded vectors, so the model takes them as inputs (`lambda_eff = sqrt(E_gap (2 Lambda - E_gap))`).
  `passes_gates` applies the verifier's gates.
- `plain_qrom_angles(R, B, J)`: the reference QROM family, `2 K (A - 2)` Toffolis with
  `K = ceil(75 / J)` and `A = 76 + R B`, plus `ceil(log2 A) - 1` scratch qubits per circuit.

State-preparation terms (`prepare_costs`) are re-derived in plain `math` from the formulas the
verifier documents (`SpinFreeData_V1`), `chi = 10`.

## Accuracy against the verifier

| | baseline (65, 60, 60), brot 12, J 8 | public refit (8, 143, 44), brot 8, J 5 |
|---|---:|---:|
| verifier score | 3,355,599,588.3155 | 299,614,422.4359 |
| model score | 3,355,599,588.3155 | 299,614,422.4359 |
| relative difference | 0 (to 1e-9 in the test) | 0 (to 1e-9 in the test) |
| `T_total`, `Q_total` | 93,237, 730 | 14,964, 427 |

Sources: baseline from one full run of the verifier's `verify()` (its summary dict, also quoted in
`SCORING_README.md`); refit from one `bench verify dfthcsos best/dfthcsos --salts 1` run
(`cost=299614422.43592083`), with `Lambda` and `E_gap` from the verifier's `evaluate_words`
applied to the `angle_words` stored in `best/dfthcsos/submission.npz`. Those words decode to the
same vectors as the circuits load: the model's score from them matches the simulated run to all printed digits.

The model is exact on both, so the 0.01% target is met with margin. It is only as good as its inputs:
a new loader family needs its Toffoli and qubit counts (from kickmix statistics) and new words need
`Lambda`, `E_gap`.

## What dominates

`score = lambda_eff * T_total * Q_total`. The 11.2x gap between baseline and refit splits as
1.05 (lambda_eff) x 6.23 (T) x 1.71 (Q).

| term | baseline | refit |
|---|---:|---:|
| `lambda_eff` | 49.301 | 46.891 |
| angle loaders Toffolis (fwd + rev) | 79,480 (85%) | 8,302 (55%) |
| outer state prep | 846 | 317 |
| inner state prep | 9,461 | 4,095 |
| Givens, `2 (N-1)(2 brot - 1)` | 3,450 | 2,250 |
| persistent prep qubits | 90 | 84 |
| word registers, `J * brot` | 96 | 40 |
| shared temporary qubits | 544 (inner QROAM) | 303 (inner QROAM) |

- `lambda_eff` barely moves (46.9 to 49.3). Both submissions sit at the gate: the refit has
  `E_gap = 3.914898000` (floor 3.914898, strict), `error_1 = error_2 = 0.02` to eight digits, while
  `Lambda = 282.8` is far above its floor of 49. `Lambda` is not binding; `E_gap`, `error_1` and `error_2` are.
- `T_total` is the angle loaders. The reference QROM costs `2 K (A - 2)` and the public refit's circuits
  cost 8,302 against 36,540 for a plain QROM of the same words (K = 15, A = 1220), so most of the
  gain over the baseline is the loader synthesis and the smaller `A`, not the factorization shape alone.
- `Q_total` is the inner state-prep QROAM's temporary workspace (303 of 427). Word registers are 9%.
  The angle circuits' own scratch (128 - 11 - 40 = 77) is far below it, so loader qubits are free up to
  the 128 cap as long as `inner_temp` dominates.

## Where the `brot` cliff comes from

The inner PREPARE picks a QROAM block exponent `k`. Larger `k` means fewer Toffolis and more temporary
qubits (`(2^k - 1) * b2 + ceil(log2(R C ceil(B / 2^k)))`, `b2 = ceil(log2 B) + 11`). With
`optimize_qubits` on, the verifier lowers `k` until that temporary count is strictly below
`brot * (N - 1)`, the qubits the Givens registers already hold. So `brot` enters the cost through a
step function: `k` drops when `75 * brot` falls to or below the temporary count of the larger `k`.

Baseline shape (65, 60, 60), `b2 = 17`:

| brot | k | inner Toffolis | inner temp qubits |
|---:|---:|---:|---:|
| 8 to 14 | 5 | 9,461 | 544 |
| 4 to 7 | 4 | 16,989 | 273 |
| 15 and up | 6 | 9,461 | 1,087 |

At `brot <= 7` the baseline shape trades +7,528 Toffolis for -271 qubits. With a plain QROM loader and
the accuracy held fixed, that is 1.33x (not 2x): the outer PREPARE's 370 temporary qubits become the
floor. The 2x in public notes is not reproduced for this shape.

The refit shape (8, 143, 44) has already used a cliff: `k = 5` needs `600` temporaries and
`600 < 75 * 8` is false (equality), so brot 8 gets `k = 4` (303 qubits, 4,095 Toffolis), while brot 9
gets `k = 5` (606 qubits, 2,991 Toffolis). At fixed accuracy and the public loaders, brot 9 would score
0.61x of the refit. There is no further cliff below 8 for this shape (the next step is at brot 3), so
`brot` 7 or 6 only trims Givens and word qubits: about 3.3% and 6.7%, if the loaders did not grow.
So the 7-bit lead only pays when the shape is such that the cliff falls at 7 and the factorization
still fits the gates; the model finds those shapes in a second.

## Reproducing

```bash
uv run pytest tests/unit/test_dfthcsos_model.py
```
