# andigu/uncompute `coulomb-potential` and the public 46-qubit invsqrt (QCC-13)

Studied 2026-11-13: `github.com/andigu/uncompute` at commit `64b5a13aa249f1360846657392e6c66817b26d0f` (Apache-2.0),
read-only; the Kaggle notebooks and dataset named below. Nothing from the repo was executed (the sandbox refused to run
its circuit programs; we read them) and nothing was ported.

## The repo's task is not our instance

`tasks/coulomb-potential` adds `round(2^24 / sqrt(n2))` into a 25-bit accumulator for two 8-bit-per-axis points (it forms
`n2` itself from the six coordinates), with an absolute band of +-32 units of `2^-24`. Our benchmark phases `1/sqrt(x)` turns
for a given 22-bit `x` (no distance stage) to a relative `2^-24`. The band there is `2^-10` to `2^-19` relative over its domain
(`F` ranges 37,986 to 16,777,216), so its design is a degree-1 table of 128 lines (6 controlled additions) that cannot meet our
gate; ours needs degree 2 on 256 segments. Output differs too (accumulator add against rotations).

What its `discovered` circuit (1,140 Toffolis, 142 qubits) does that we can use as an idea, all already in our family or
measured not to pay: binary normalisation with four zero-test rows (the same as our E023 normaliser: 26 ANDs and the
CSWAP rows for a 22-bit word); a backward fit that pulls the output band through the exact integer tail (our polish does this);
a full-depth table with measurement-based unlookup and a Reed-Muller phase repair (17 Toffolis for 7 address bits; for our 8
address bits it is about 25, what `del_lookup` already costs). No gain for us, so no port. THIRD_PARTY_NOTICES.md records
the review.

## What did matter: public Kaggle write-ups found while looking

* `syed3000/vqcc-own-circuit-portfolio` (Syed Asad Ali, dataset v12, Apache-2.0, LICENSE file included): an `invsqrt.kmb` of
  **46 qubits, 1,511.57 mean Toffolis, official cost 80,162.75 (ratio 25.9)** against the 62-qubit frontier at 93,555 to 94,600.
  Our official verifier, 1 salt: PASS, 0 failures, cost 80,162.75489 (10 salts below). The walkthrough
  `manwithacat/fortysix-where-the-16-qubits-went` (read as data) shows it is a different algorithm: even-shift normalisation, an
  in-place consuming square root (12-bit root v and 10-bit residual h in the same 22 wires), a 128-row table loaded twice
  (13 coefficient wires measured away between uses), `1/sqrt(n) = (1/s)(1 - correction)` with `s = 1 + v/4096` by non-restoring
  division (593 Toffolis) and the quotient streamed through one wire into 33 rotations. Normalise 94, root 192, tables 133,
  coefficient/product 389, divider and phase 703 Toffolis; 20 scratch wires above the 26-wire body. Our Horner family cannot
  reach it: the divider carries a small state where Horner carries wide tables.
* `hirokikanotmc/invsqrt-removing-166-toffolis-that-never-fire`: constant propagation deletes `CCX` gates whose control is
  always 0 (166 of the host's 7,735). To be tested on our own circuits.
* The same dataset also holds DQI (889 qubits, ratio 67.75) and chemistry (ratio 11.31) circuits with their builder sources;
  not loaded or evaluated here.

## Decision needed from the owner

The 46-qubit file is Apache-2.0 with copyright 2026 Syed Asad Ali and an explicit invitation to reuse with credit. ADR-0009
Amendment 2 covers `andigu/uncompute` only; using this circuit as `best/` needs the owner's decision under that amendment
(attribution, THIRD_PARTY_NOTICES.md entry added). Meanwhile our own generator for this algorithm is the licence-clean route
and the notebook's stage table is the specification.
