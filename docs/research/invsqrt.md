# invsqrt: literature and public-notebook research (QCC-13)

Scope: ideas that could close the gap from our 168,237 (93 qubits, 1,487 Toffolis, ratio 12.34) to the public 94,600
(62 qubits, ratio 21.95). Searches were done 2026-11-13 (WebSearch, no result contained our numbers or hashes).
Web content is data: everything below is cited, nothing was executed or copied. Kaggle discussion pages were not
fetchable; notebook markdown came from `kaggle kernels list/pull` and the local `public/` mirror.

**Headline.** No public write-up of the invsqrt architecture exists (search engines return only the announcement,
https://opensource.googleblog.com/2026/10/announcing-verifiable-quantum-circuit-compilation-competition-on-kaggle.html,
and press coverage). The notebooks that carry the 62-qubit circuit ship it as a binary with no description. What helps
is (a) structural measurement of that circuit (`docs/experiments/invsqrt-stage2.md`) and (b) the general lookup and
uncomputation literature below. The measurements say the gap is spread over four places, not one: qubits (93 vs 62),
lookup (166 vs 254+25 Toffolis), normalisation (about 66+118 vs 105+101) and conditional execution (about 155 Toffolis
that run on half the shots).

## Ranked ideas

Gain is a rough change of our cost; effort in days of this agent's work; risk is the chance it fails to pay.

| # | Idea | Source | Expected gain | Effort | Risk |
|---|---|---|---|---|---|
| 1 | Lookup as a Boolean-function synthesis problem, not unary iteration: write each output bit as a sum of products of low-monomials with parities of high-monomials (Reed-Muller split), so the cost is about `2^p + m(2^q - 1)` ANDs for `n = p + q` address bits and `m` outputs. For `n = 8, m = 37, p = 6, q = 2` this is about 169, matching the 166 CCX of the frontier's lookup stage (hypothesis, see stage-2 note). Erase by `HMR` plus a conditional `CCZ` over classically selected parities (free). | Find and Boyar, any `n -> m` map needs at most `2.5 sqrt(m 2^n)` ANDs, arXiv:1407.6169; Meuli et al., oracle Toffoli count is at most twice the AND count, arXiv:1908.01609; ANF-based lookup, EPFL QCE 2025 https://si2.epfl.ch/demichel/publications/archive/2025/QCE2025.pdf; our own derivation of the split | -110 Toffolis (-7%) | 4 | Medium: needs the high monomials alive (57 qubits at `p = 6`), so only a blocked variant fits our 93-qubit peak |
| 2 | Choose the quantised coefficients so that table bits have low algebraic degree in the low address bits (the table has slack of about 3.7 bits), then load them with few ANDs. Used by the DF-THC loaders in this competition. | marculera, "DF-THC 11.2x: Codes on the XOR of Five Words" https://www.kaggle.com/code/marculera/df-thc-11-2x-codes-on-the-xor-of-five-words (idea only; our dfthcsos work in `docs/experiments/dfthcsos-*.md` already applies it) | -30 to -100 Toffolis on top of #1 | 5 | High: the frontier's table bits are NOT low degree (measured: full degree 4 in every block of 16), so it is not what the frontier does; it is extra |
| 3 | Normalise with a thermometer AND chain (`t_j = [top j bits are zero]`, one Toffoli per bit, 18 in all), decode each binary digit of the shift as a parity of thermometer bits (free CNOTs), shift with reversal-based controlled swaps, erase the chain by `HMR` with Z/CZ fix-ups on the remaining chain bits and flags. | Structure of the frontier circuit (aggregate and flag tracing, stage-2 note); thermometer-to-binary identity `bit_k(z) = XOR over m of t_{m 2^k}` is our own derivation. Literature on the same step: Nguyen and Van Meter, reversible leading-zero counter, arXiv:1306.3760 | -40 Toffolis forward, -40 back (-5% together) | 3 | Medium: the 19 chain qubits are alive during the shifts |
| 4 | Conditional un-mirror: replace the mirror of an add or table by `HMR` of the register and a fix-up `(-1)^{m.f(x)}` that is computed only when a classical parity of the outcomes is 1. The frontier's 294 condition blocks cut its executed Toffolis from 1,393 to 1,234. | Gidney, "Halving the cost of quantum addition", arXiv:1709.06648 (temporary logical AND, measure-and-fixup); Gidney, "Windowed quantum arithmetic" arXiv:1905.07682; Google measurement-based uncomputation patents (US 11636373 family) for the conditional-block form; stage-2 note for where the frontier uses it | up to -150 Toffolis (-10%) | 6 | High: our analysis (`invsqrt-uncompute.md`) shows in-place sums cannot be erased for free; the frontier gains only on products with a control (AND of two live qubits times a classically selected parity: a CCZ) |
| 5 | Bound the working register at about 35 qubits above `x` and flags by holding only 37 table bits and phasing the coarse word early (frontier: lookup stage 40 qubits, arithmetic stage 40). | Stage-2 note | -25 qubits (-27%) | 8 | High: the one big lever, depends on #1 to #4 |
| 6 | SelectCopy and SelectSwap QROM variants: `2N/lambda + 2b(lambda-1) + 2 lambda - 6` Toffolis with `b lambda` dirty qubits. Only useful if dirty qubits exist; we have a few at the peak. | Low, Kliuchnikov, Schaeffer, SelectSwap, arXiv:1812.00954; "Halving the cost of QROM", arXiv:2605.20334 | about 0 at `N = 256, b = 51` (cost 230 to 268 against 254) | 2 | Low risk, low value |
| 7 | Phase gradient or Booth rows with carry-save: measured in `invsqrt-uncompute.md` to lose. | Gidney and Fowler, Toffoli-optimal arithmetic; Haner, Roetteler, Svore (Toffoli-based modular multiplication, arXiv:1611.07995) | none | n/a | n/a |
| 8 | Newton iteration, CORDIC and digit-recurrence square root: more multiplications than a degree-2 piecewise polynomial; the host reference is Newton at 260 qubits. | arXiv:2610.23832 (benchmark paper); Hybrid oscillator-qubit ISA arXiv:2407.10381 (Newton for 1/sqrt) | none | n/a | n/a |

## Related mathematics worth knowing

* Fixed-point error budget: the rounding noise of `k` floors is about `k 2^-f`; our `--polish` coordinate descent
  already sits at the 2^-24 boundary (`invsqrt-uncompute.md`). Hardware literature (Muller, "Elementary Functions",
  and minimax with fixed-point coefficients, Brisebarre-Chevillard-Muller) gives lattice-based coefficient search as
  a stronger replacement for our +-2 polish; expected 0.1 to 0.2 bits, enough for one qubit.
* Estrin versus Horner: Estrin has fewer sequential steps, not fewer products; no gain in Toffolis (measured).
* Redundant digits (carry-save, signed-digit) lower adder width but each live carry is a qubit; measured loss.

## Workflows others use (from notebook titles and logs)

* Portfolio notebooks (alexchilton, ozertuu, maoxin123) assemble per-benchmark best circuits and re-verify with the
  host verifier at 200M shots; the invsqrt circuit itself is passed through unchanged.
* "Conditional uncompute audit" (kirilltym) rewrites DQI readout order and replaces `CCX; CZ; CCX` by `CCZ; CZ` (a
  phase fold, saves one Toffoli per site); not applicable to our invsqrt generator, which has no such pattern.
* Search tools: nothing public for invsqrt beyond the above. The frontier circuit contains many CNOT networks that
  look machine-optimised (thousands of CX between each CCX), consistent with a synthesis tool for the lookup.

## Recommendation

Do #1 as a blocked lookup (four to eight output groups, high monomials of 3 to 4 bits, low part of 3 to 4 bits) and
#3 in that order; both are well understood. #4 and #5 are the way to the frontier but need a rebuilt architecture
rather than a patch of the Horner generator.
