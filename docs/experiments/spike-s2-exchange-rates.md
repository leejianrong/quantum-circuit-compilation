# S2: exchange rates per track (QCC-60)

Question: what is one qubit, one Toffoli, one rotation or one unit of `Lambda` worth on each track, at the
frontier? The scores are products of powers (`docs/learn/costs-and-mbuc.md`), so the rates are exact algebra
(`src/bench/rates.py`, tested against finite differences). Inputs are measured: invsqrt 44 qubits, cost 75,170.66
(syed3000 v13 as reported, not yet verified by us); DQI public 890 qubits, 367,878 mean Toffolis (balram's
log) and our `fixed4` 889 qubits, 384,762 static; dfthcsos 427 qubits, 14,712 Toffolis (balram's log).
[V] for the inputs, [M] for the algebra.

## Rates

| Track | 1 qubit is | 1 Toffoli is | 1 qubit = Toffolis |
|---|---:|---:|---:|
| invsqrt (Q*C) | 2.27% | 0.0585% | 38.8 |
| DQI (R Q^2 T), public 890 | 0.225% | 0.00027% | 827 |
| DQI, ours (889, 384,762) | 0.225% | 0.00026% | 866 |
| dfthcsos (lambda_eff T Q) | 0.234% | 0.0068% | 34.5 |

* **Rotations (invsqrt).** The 34 rotations cost 7.35 Toffoli-equivalents each, that is `log2(1/eps)` = 43 bits,
  and together 14.6% of the cost. Removing one bit of synthesis precision from all of them saves 0.28%, so rotation
  precision is a small lever; removing one rotation saves 0.43%, as much as 7 Toffolis.
* **Lambda (dfthcsos).** `d ln lambda_eff / d Lambda = 1/(2 Lambda - E_gap)`: 0.178% per unit at `Lambda` = 283.
  Our `Lambda` of 490 to 560 costs `lambda_eff` a factor 1.32 to 1.41 against 283.
* A 1% cut on one track moves the geometric mean by 0.33%, on any track.

## Where the dfthcsos gap sits

Own words, own loader: 2.50x. Own unary loader on the public words: 6.85x (E001, row `997264ad`). Public: 11.31x.
So 11.31 / 2.50 = 4.52 splits into 1.65 for the loader (public 11.31 against our 6.85) and 2.74 for the words
(6.85 against 2.50). `Lambda` explains about 1.32 to 1.41 of the 2.74 [I, our `Lambda` per fit, not measured on the
E040 words themselves]; what remains, about 1.9 to 2.1, is the 11-bit words against 8-bit (more planes, more Toffolis
and qubits). Neither the `Lambda` penalty (S4) nor 8-bit rounding alone closes the words gap; both are needed.

## Lessons

* The claim "one qubit is worth about two Toffolis" (DQI) was wrong as a unit statement. It is 1% of qubits = 2% of
  Toffolis; one qubit is about 830 to 870 Toffolis. See the correction entry.
* A qubit is 0.23% of the score on DQI and dfthcsos but 2.27% on invsqrt, because invsqrt has 44 qubits and the others about 900 and 430. In Toffolis the order differs again (39, 830, 35).
* Ranking by gap to the public frontier and by cost of the closing lever: dfthcsos words (S4) first, then invsqrt
  structure (S3, tasks 3), DQI last (the whole remaining gap is under 0.5%).

Reproduce: `PYTHONPATH=src python -c "from bench.rates import Point; ..."` (see `tests/unit/test_rates.py`).
