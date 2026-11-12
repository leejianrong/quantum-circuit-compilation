# DQI small-field instances (QCC-18)

`src/dqi_gen/instances.py` builds a decoder for a smaller code and runs the **official** verifier on it,
so a design change can be checked in seconds instead of on Kaggle. The verifier already accepts any
`ProblemSpecDQI(m, n, degree, r, num_shots)` (`benchmark_instance` takes each as a keyword), so nothing
was re-implemented: `r` defaults to the bent-function size `(q - isqrt(q)) // 2` for that field, the DQI
weight distribution is recomputed for `(m, n, q, r)`, and the register names (`S0..`, `E0..`) are unchanged.

| name | (m, n, b) | l = n/2 | field |
|---|---|---:|---|
| tiny | 15, 4, 4 | 2 | GF(16) |
| small | 63, 10, 6 | 5 | GF(64) |
| medium | 255, 20, 8 | 10 | GF(256) |
| large | 1023, 40, 10 | 20 | GF(1024) |
| full | 4095, 70, 12 | 35 | the benchmark (Kaggle only) |

```text
QCC_DATA=data uv run python -m dqi_gen.instances --gen reference --instance small
```

Two traps found while setting this up:

- **Shot floor.** With zero failures the Clopper-Pearson bound is `1 - 2^(-128/N)`, which is below 1/16 only
  from about 1,376 shots. Fewer shots raise "Effective error rate >= 1/16" even for a perfect circuit.
  `min_shots()` returns 1,536 (a multiple of the 256 batch size); the default here is 3,072.
- **The score `R * Q^2 * T` is meaningless at low shot counts** because `R` depends on `eps_plus`. The tool
  also reports `q2t = Q^2 * T`, which compares designs directly.

Reference decoder (host Apache-2.0 builder), 3,072 shots, one core, wall time including the build:

| instance | qubits | Toffolis per shot | Q2T | wall |
|---|---:|---:|---:|---:|
| tiny | 115 | 22,090 | 2.92e8 | 0.9 s |
| small | 229 | 93,542 | 4.91e9 | 1.4 s |
| medium | 462 | 326,559 | 6.97e10 | 3.3 s |
| large | 972 | 1,558,907 | 1.47e12 | 37 s |

`large` is the largest that stays comfortable on this laptop. The same tool verifies our own generator
(`--gen divstep`, QCC-19, `docs/experiments/dqi-divstep-v0.md`).

Tests: `tests/unit/test_dqi_instances.py` (marked `integration`, needs `data/`) checks that the reference
passes tiny and small, that a decoder that does nothing is rejected, and that the shot floor is enforced.
