# dfthcsos: fewer than 8 bits per angle word (QCC-38, QCC-15)

Question: can mixed angle widths, or rounding that targets the verifier's gates instead of the angle
error, get `brot <= 7` through the accuracy gates, and would it pay? Short answer from this round: no.
The 7-bit design we built fails `error_2` by 8.8x, and the cost model says that even a passing 7-bit
design on the public shape saves only about 3%. Numbers below; all start from the public refit
(`best/dfthcsos`, shape (8, 143, 44), 8-bit words, cost 299,614,422.44). Cost-model terms are in
[dfthcsos-cost-model.md](dfthcsos-cost-model.md).

## What the gates are made of

For the public refit:

| quantity | value | gate |
|---|---:|---:|
| `error_1` | 0.0200000 | 0.02 |
| `error_2` | 0.0200000 | 0.02 |
| `E_gap` | 3.914898000 | > 3.914898 |
| `Lambda` | 282.8 | > 49.0 |

It sits on three gates at once. Three facts about how the metrics depend on the words (all from the
verifier's own `evaluate_words`, ~3 s per call, no circuits needed):

1. `error_2`, `Lambda` and `E_gap` depend only on the two-body words (and the weights `w`, `W`).
   The one-body rows enter only `error_1`.
2. `error_1` is the fit of the 76 one-body rows to the eigenvectors of `h1_prime`, which the verifier
   rebuilds from the *decoded two-body vectors*. Perturbing the two-body words and leaving the
   one-body rows alone blows `error_1` up (random +-1 ulp on 1% of two-body words: `error_1`
   0.02 to 0.23). Re-deriving the one-body rows after any two-body change removes most of that, so
   do it every time.
3. Rounding noise raises `E_gap` (the `sum|lambda| - sum lambda` term grows), so a noisier table
   costs `lambda_eff` as well as risking the gate: `lambda_eff = sqrt(E_gap (2 Lambda - E_gap))`.

The public one-body words are better than nearest rounding: nearest rounding of the exact eigenvectors
at 8 bits gives `error_1 = 0.0548`, the public words 0.0200. They have been optimised.

## Experiments

### 1. Truncate low bits where the angle carries little amplitude (mixed widths)

An angle on tree edge `(p, c)` rotates the amplitude that reaches that edge, so an angle with small
carried amplitude changes the vector little. Among the 1144 two-body rows, the fraction of angles with
carried amplitude below 0.01 / 0.03 / 0.1 is 17.9% / 42.9% / 67.2% (one-body rows: 3.4% / 9.4% / 34%).
Rounding the lowest bit of those words to even (a 7-bit word in an 8-bit register), one-body rows
refit by nearest rounding:

| words changed | `error_2` | `E_gap` | `lambda_eff` |
|---|---:|---:|---:|
| none (public) | 0.0200 | 3.91490 | 46.891 |
| carried amp < 0.01: 7,570 | 0.0206 | 3.91592 | 46.897 |
| carried amp < 0.05: 23,633 | 0.0348 | 3.98270 | 47.298 |

Even the smallest step breaks the `error_2` gate, because the public words have no slack to spend.
Mixed widths cannot be tried on the public table without refitting the whole factorization.

### 2. Plain requantization to 7 and 6 bits

Nearest rounding of the public two-body words (one-body rows refit): 7 bits gives `error_1` 0.137,
`error_2` 0.425, `E_gap` 9.45; 6 bits gives 0.361, 0.728, 15.8. Refitting the weights `w` helps
little: at 8 bits 0.0200 to 0.0198, at 7 bits 0.425 to 0.296.

### 3. Gate-targeted rounding: progressive rounding against `error_2`

`scripts/dfthcsos_low_brot.py` fits angles and weights continuously, then fixes the words closest to
the 7-bit grid in stages (30, 50, 70, 85, 95, 100%) and re-fits the rest with L-BFGS. The `error_2`
objective is exact through Gram matrices (`error_2^2` is a quartic form in the vectors) and matches
the verifier to eight digits, with analytic gradients checked against finite differences.

| stage | `error_2` |
|---|---:|
| continuous angles and weights (the shape's floor, not converged) | 0.0192 |
| 50% fixed | 0.0193 |
| 70% fixed, after re-fit | 0.163 |
| 85% fixed | 0.179 |
| 100% fixed | 0.177 |
| 100% fixed, weights re-fit | 0.175 |

Half of the 8-bit words are even, so they sit on the 7-bit grid for free. The cliff comes when the odd
ones are forced off their optimum, and re-fitting the others cannot compensate. For comparison, the
public notes report a plateau near 0.11 for `error_2`; we are in the same region.

### 4. A real candidate, checked with the real verifier

Candidate 7-bit table: the progressive-rounding two-body words, weights re-fit, one-body rows refit to
the new `h1_prime` (nearest rounding 0.113, then coordinate descent on `error_1` to 0.030). Circuits
come from the host's reference QROM generator (`J = 5`, 15 circuits); no third-party circuit files
are committed. `bench verify dfthcsos <dir> --salts 3`:

```
FAIL failures=3/3  error_1 = 30.2884 mHa > 20 mHa; error_2 = 175.2625 mHa > 20 mHa
```

`Lambda` 300.9 and `E_gap` 6.229 pass their floors, but `E_gap` is 59% above the floor, so the
candidate would score with `lambda_eff = 60.9` (public: 46.9), 30% worse, before any loader effect.
(Scaling `W` to bring `E_gap` down, tried in an earlier version of the script, does not work: the gap is not monotone in the scale and the
minimum is near the public value.)

Positive control for the model: the public 8-bit words through the same reference QROM generator
(`J = 5`) PASS 3/3 salts at 865,005,498.40. The model predicts 865,005,498.4012733 from the
statistics alone (angle Toffolis 36,540, 61 qubits), an exact match, which also shows how much the
public loader synthesis is worth: 8,302 vs 36,540 angle Toffolis, 2.89x on the whole score.

## Would 7 bits pay if it passed?

The cost model, with the loaders unchanged (an upper bound for the saving):

- On the public shape, `brot` 8 to 7 trims the Givens term (-300 Toffolis) and 5 word qubits:
  score x 0.968. `brot` 6: x 0.937. There is no `k` cliff left below 8 for this shape, because the
  refit already sits just under it ([cost-model note](dfthcsos-cost-model.md)).
- The continuous floor of the shape is `error_2` = 0.0192 against a gate of 0.02. At 8 bits the public
  rounding costs only sqrt(0.0200^2 - 0.0192^2) = 0.0056 in quadrature. A 7-bit design needs rounding
  noise below roughly that, 30x lower than the 0.175 reached here. The only other way to make room is
  a larger factorization (lower floor). With angle loaders scaling with the number of addresses
  (an assumption), the score relative to the public refit is:

  | B | 8 bits | 7 bits |
  |---:|---:|---:|
  | 143 | 1.000 | 0.968 |
  | 150 | 1.050 | 1.018 |
  | 160 | 1.111 | 1.078 |
  | 200 | 1.310 | 1.275 |

  So a 7-bit design pays only if it needs less than about 3% more addresses (B up to about 147).

## Verdict

Not a verified improvement; QCC-38 and QCC-15 stay open. What the numbers say:

- The 7-bit cliff is a rounding-noise problem on the two-body words, not a hard limit, but the gap is
  large: 0.175 vs 0.02 with a first-order optimiser, and the public shape has only 0.0056 of budget.
- On this shape the best case for 7 bits is about 3%, so it is not worth more optimiser effort here.
- The 2x cliff in the public notes belongs to shapes like the baseline's (65, 60, 60), where `brot`
  7 drops the inner QROAM block exponent; the model gives 1.33x there at fixed accuracy, and the refit
  has already taken that step at 8 bits.
- The largest untouched lever is the loader synthesis (55% of Toffolis, 8,302 per family). Any new
  word table needs a loader generator before it can be scored: the reference QROM costs 4.4x more.
  The public circuits compute a few hundred AND monomials of the address bits with Toffolis and fan the
  results out with CNOTs, apparently exploiting the unused addresses 1220 to 2047. Writing a generator
  for that structure is the next step, and it would make word tables that are cheaper to load (fewer
  distinct monomials) worth optimising for.

## Reproducing

```bash
QCC_DATA=$PWD/data uv run python scripts/dfthcsos_low_brot.py check best/dfthcsos 7
QCC_DATA=$PWD/data uv run python scripts/dfthcsos_low_brot.py round best/dfthcsos 7 /tmp/out7
QCC_DATA=$PWD/data uv run python scripts/dfthcsos_low_brot.py finish best/dfthcsos 7 /tmp/out7
```

`round` takes about 20 minutes on a free machine (about 5 s per gradient with 6 threads under load).
