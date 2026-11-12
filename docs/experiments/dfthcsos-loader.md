# dfthcsos: our own angle loader (QCC-49, QCC-16)

`src/dfthcsos_gen/` builds the `ANGLE_k` family from a word table. Stage 1 of ADR-0009 (paper first): unary
iteration (Babbush et al., arXiv:1805.03662) with two prunings (a subtree whose rows agree loads once at its
root; an all-zero subtree costs nothing). Tests: `tests/unit/test_dfthcsos_gen.py`.

## Result: wider circuits, not cheaper circuits

A unary loader costs `A - 2` Toffolis per circuit whatever the word width (the words are CNOT fan-out), so
the only lever is the number of circuits `K = ceil(75 / J)`. `J` is capped by the 128-qubit limit:
`11 + J * brot + 10 <= 128`, so `J = 13` at `brot = 8` (125 qubits) and `K = 6`, against `J = 5`, `K = 15`
for the public circuits.

Public refit words (8,143,44), 8 bits, loaded by our generator, `bench verify dfthcsos --salts 3`
(experiment E001):

| loader | circuits | angle Toffolis (both passes) | qubits | cost | ratio |
|---|---:|---:|---:|---:|---:|
| host reference QROM, J = 5 | 15 | 36,540 | 61 | 865,005,498 | 3.88 |
| ours, unary, J = 13 | 6 | 14,616 | 125 | 489,890,973 | 6.85 |
| public loaders, J = 5 | 15 | 8,302 | 128 | 299,614,422 | 11.20 |

PASS at 3/3 salts. The cost model predicted 489,890,973.1788 from the statistics alone and the verifier
returned the same number, so the model also covers a loader we generate ourselves. Trade-off at `J = 13`:
angle Toffolis fall 2.5x against the reference at `J = 5`, `Q_total` rises 427 to 491 (104 word qubits
persist), net 1.77x better than the reference.

## Why we are 1.64x behind: the public loaders are not a unary iteration

For these 35-bit-wide delta tables a unary loader needs one Toffoli per address, and a counting
argument says a generic table needs about the same: a circuit of `T` ANDs with free CNOTs has about
`T^2 + 62 T` bits of freedom, and a generic table carries 35 x 1220 bits, so `T` is at least about 180
for any circuit and a sum of products over a fixed variable set (Lupanov or tensor style) is above 400.
The public circuits cost 270 to 296 Toffolis each, so their tables must lie in a structured family.

Checks on the public table (analysis of the data, nothing copied): the 40 delta bit columns have GF(2)
rank 35 (the top bit of the five words of a row agree); every bit matrix with a 7 x 4 or 5 x 6 split of
the address is full rank; the table is not inside any Reed-Muller code of degree up to 6 (it is not
low-degree). Aggregate gate statistics of one public circuit (ADR-0009 stage 2, logged in
`docs/PROVENANCE.md`): 291 CCX, 41,645 CX, 75 measured temporary ANDs; about 75 CCX build products of the
high address bits into ancillas, and about 200 CCX control on address bits XORed in place with those
products and target word bits directly (about 5 per output bit). So each bit is a rank-5 quadratic form over
about 86 variables, which fits 860 of the 1,220 bits an unconstrained bit would have: the angle table was
fitted to the loader, not the other way round.

## Next lever

A loader of that kind is cheap only for tables inside its family, so the work is a co-design: fit angles
and weights jointly with a per-bit rank budget against the verifier's `error_2` gate. That is a
discrete optimisation inside a gate the public refit already sits on (0.0200 of 0.0200), so we have not
tried it yet. It would take the loader from 14,616 to about 8,300 Toffolis (cost-model ratio 6.85 to 11.2)
with the loaders' qubits (126) already inside the shared workspace.

## Reproducing

```bash
# build the loaders for the public words (data stays local), then verify
uv run python - <<'EOF'
import numpy as np
from dfthcsos_gen import build_family, write_family
w = np.load("best/dfthcsos/submission.npz")["angle_words"]
write_family(build_family(w, 8), "/tmp/run_j13")
EOF
cp best/dfthcsos/submission.npz /tmp/run_j13/
flock /tmp/qcc-heavy.lock env QCC_DATA=$PWD/data uv run bench verify dfthcsos /tmp/run_j13 --salts 3
```
