# dfthcsos stage 2: public ideas, our own seed (QCC-16, QCC-15)

ADR-0009 amendment of 2026-11-13 allows study of public work and online research. Research summary and
ranked ideas: [docs/research/dfthcsos.md](../research/dfthcsos.md). Everything implemented is ours.

## Finding that matters

The public notebook text (marculera) says the frontier tables come from a seed built from the target alone
(pivoted Cholesky leaves, balanced k-means into groups, simultaneous OMP, least-squares weights) and a very
long fit (60k-iteration L-BFGS rounds, then 33-stage progressive rounding, Adam), reaching 12 mHa at the
scoring shape. Our random-start fit stalls at 28.8 mHa, so the seed and the fit length are the gap, not the
rounding schedule (consistent with dfthcsos-eight-bit.md). Other ideas (coded bit 0, row dealing, Newton refit of
W and H2) are logged but not built.

## Experiment: our compact seed, from the description (negative so far)

`src/dfthcsos_gen/seed.py`, `scripts/run_fit.py --init compact`. Shape (8,143,44), laptop, 4 threads,
about 0.5 s per L-BFGS iteration. Own `tsym` from the FCIDUMP (not committed).

| iteration | compact seed `error_2` | random start (E003, same shape) |
|---:|---:|---:|
| 0 | 2.12 | |
| 100 | 0.617 | 0.446 |
| 200 | 0.349 | 0.219 |
| 400 | 0.229 | 0.122 |
| 700 | 0.176 | 0.083 |

Our seed is worse than a random start at equal iterations. The 2.12 start error shows the OMP step is weak:
the 44 leaf matrices per group are nearly full rank (76), and with 12 candidate eigenvectors per leaf and
B = 143 shared vectors the group cannot represent them. Not yet tried: all 76 eigenvectors as candidates, more
leaves than R*C (they used 414 for 360 slots and let the fit drop some), the best of 500 k-means starts by
orbitals per group, weighted least squares, and a fit of tens of thousands of iterations (their advantage
showed over 60k iterations, not 700). The run was stopped at 700 iterations. No verifier run is justified;
the ledger is unchanged.

## Status

Best verified fully-own result is unchanged: 1,697,674,805 (ratio 1.98, 3/3 salts, 11-bit words). The two
Kaggle fits (`qcc-dfthcsos-fit`, `-fit-b`) were not touched. Next lever: finish the seed (items above) and run it
for 10+ h on a Kaggle kernel; then progressive rounding at 8 bits on a base below about 14 mHa.
