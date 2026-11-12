# DQI: cutting qubits in our own divstep decoder (QCC-19)

Cost is `R * Q^2 * T`, so a qubit saved is worth two Toffolis. Starting point
(`docs/experiments/dqi-divstep-v0.md`): 4,013 qubits, 1.04M Toffolis, official 1.9973e13 (ratio 1.224, 5/5 salts).
Every change below was checked with the official verifier on the small instances (seconds, same generator code)
and on `narrow` (full `n` and field, 71 positions, 25,600 shots). Full-size numbers are the static count
`narrow + 4,024 x 108` Toffolis (the Forney sweep is exactly 108 per position) and the same qubit count, then
confirmed on Kaggle.

## What worked

| step | qubits | Toffolis (full size) | `Q^2 T` | change |
|---|---:|---:|---:|---|
| v0 (QCC-19 first merge) | 4,013 | 1,041,122 | 1.68e13 | |
| 1. freeze the dead f row | 3,243 | about 1.10M | 1.16e13 | `fv` window stays at t + 1 registers |
| 2. Omega in place in `S_0..S_{t-1}` | 2,835 | 1,141,782 | 9.18e12 | no Omega registers |
| 3. row ranges by step, free early shift, no unused scratch | 2,776 | 1,017,112 | 7.84e12 | -35 qubits, -124k Toffolis |

**1. The f row is dead once it overflows.** `v_f` is relabelled up by `z` every step, and in v0 the coefficient
pushed past index `t` was kept as garbage: 70 extra registers (840 qubits). Decodable syndromes have linear
complexity at most `t` throughout (Berlekamp-Massey keeps it monotone), so a row whose degree would pass `t` can
never be added or swapped in again: every later discrepancy is zero. The shift is therefore controlled: shift
while `fv[t] == 0`, freeze otherwise, one `sh` bit per step recorded for the reverse pass (the freeze cannot be
recomputed from the after-state: a frozen step and a shifted step can leave the same top and bottom). Cost:
the flag (11 Toffolis, uncomputed by measurement) and a controlled cyclic shift (`t` cswaps of 12 qubits per step,
forward and back). Dropping the tail without the flag fails the verifier (value errors on 83% of shots), so the
tail is genuinely nonzero, just never read.

**2. Omega lives in the syndrome registers.** After the forward pass `sigma` is scaled in place by
`mu = 1 / sigma_0` (35 products, each coefficient cleared as `lam * y` by measurement: no Toffolis for the clear),
`gv[0]` keeps `sigma_0` as the scale and `sigma_0 = 1` is implicit (an `X` on the evaluation register).
Then `S_i <- S_i + sum_{k=1..i} sigma_k S_{i-k}` for `i = t-1 .. 0` (descending, so every `S_{i-k}` read is
still original) is exactly `Omega_i`. Forney reads Omega from those registers; `Omega` and the scaling are
undone before the reverse pass, which needs the original syndromes. -420 qubits for +0 registers; the Omega
clear costs 595 products instead of a free measurement (+40k Toffolis).

**3. Bounds that follow from the step index.** Before step `k` both rows have degree at most `k`, so the row
update, the row swap and the f shift run on `min(t, k) + 1` registers; for `k < t` the f row's top register is
zero, so the shift is a free relabelling and needs no `sh` bit. The Forney scratch `inv` and `located` were only
used by the odd-degree fallback and are no longer allocated on the tower path.

## Where the remaining qubits are (2,776)

| piece | qubits |
|---|---:|
| syndromes (read-only, Omega in place) | 840 |
| `v_g` + `v_f` | 864 |
| dialog: `c` 70 x 12, `sw` 70, `sh` 35 | 945 |
| `b`, `delta` | 20 |
| Forney scratch (3 evaluation registers, zero test, tower, `mu`) | about 107 |

The peak is the Forney sweep. At the end of the forward pass the live set is 2,669.

## What did not work or is not worth it

- **Erase `S_{t..n-1}` during Forney** (they are the LFSR extension of `S_{<t}` under `sigma`, so
  `S_i += sum sigma_k S_{i-k}` clears them with 1,225 products and the same again to rebuild): -420 qubits at
  Forney, but the forward-end live set is already 2,669, so the peak only falls by about 107 (4%) for +154k
  Toffolis (+15%). Net loss. Erasing only 9 registers would just reach the forward-end peak (+40k Toffolis,
  -3.7% cost): not done.
- **Dropping `sw`/`sh`/`c`.** `sw` is not recoverable from the after-state (a swap and a no-swap step with
  `c != 0` can both leave `delta <= 0`), `sh` likewise; `c` is real information: `d = c b` is lost by the
  update, and `[z^k](v_g' S) = 0` for every `c`. The dialog is at its information minimum (70 x 12 bits is the
  entropy of `S`).
- **Euclid-order (reciprocal) divsteps with the paper's poly + dialog shared register** (arXiv:2510.10967
  section II B 3): classical check on GF(64): `(f, g) = (1, rev_n S)`, `delta = 0`, `n + 1` steps leaves
  `sigma` reversed in the g row for every weight 0..t (`delta = 1` fails at weight `t`). Exact polynomials, so
  no tail, but `len(f) + len(g) + len(dialog) = 2n + 2` slots: the end state `(r_{i-1}, r_i)` is a second copy of
  the information the dialog holds, so it is no smaller than `S` + dialog (840 + 840). It also needs
  data-dependent loop bounds (`(len + delta) / 2`) in the subtraction. Not implemented.
- **Series form (`G` in place of `S`, dialog in the freed slots).** Discrepancy becomes a direct read (no
  convolution, -119k Toffolis) but the F series needs `n - k` slots and its dropped coefficient each step is
  real data: 840 qubits of garbage replace the 840 of `S`. No gain.
- **Per-position Forney** is at 108 (norm 21, GF(2^6) inversion 28, two products 42, gate 6, zero test 11); a
  Horiguchi-Koetter variant (no Omega) needs a product of two evaluations under the inversion, so it is worse.

## Next lever

Both copies of the information are alive at the Forney peak: `S` (840) and the dialog (840), plus `sigma` and
the f row (864). The public frontier (about 892 qubits) must hold one: an in-place bijection
`S <-> (sigma, Omega)` with no dialog, i.e. an in-place reversible Berlekamp-Massey. The obstruction is that
the quotient `c` of a non-swap step is not a function of the after-state of the rows, so any such design needs
a different state than `(S, v_g, v_f)`. The only parts of the 2,776 that this architecture can still shed are
about 100 qubits of Forney scratch and `sw`/`sh` (105).
