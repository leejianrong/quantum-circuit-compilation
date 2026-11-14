# DQI gap survey: our `fixed` circuit (65.77x) against syed3000's (67.4x) (QCC-19)

Question: the extract stage is the public kernel verbatim, the extract plus synthesis round trip is within 0.6% and the mask gauge is
worth at most 0.2%. Where is the rest of the gap, and which decoder-design changes could close or beat it?

Labels: **[M]** measured from a file or a ledger row in this pass, **[D]** derived arithmetic from [M] numbers, **[R]** read in the vendored
Apache-2.0 source (`third_party/syed_dqi/`, read only, nothing run), **[G]** guess. The score is `R * Q^2 * T`, so one qubit is worth
`2T/Q = 879` Toffolis (0.225% of the score) and 1,000 Toffolis are 0.256%.

## What is and is not on this machine

* syed3000's `dqi.kmb` (sha `7cbe8ecf`) and his full source tree are **not** here (`public/` has no syed3000 files; `~/qcc-circuits/` does
  not exist on this machine). All syed numbers below come from our ledger row 84 (Kaggle, 5 salts): 889 qubits, 384,003 Toffolis,
  `salt_costs` 360.73e9 (3 salts) and 362.39e9 (2 salts). There is **no per-stage breakdown of syed's circuit** in this pass.
* Ours: `~/qcc-fits/kaggle/leejianrong__qcc-dqi-gen/fixed.kmb` (350 MB, sha `37d8047d`), streamed once with `dqi_gen.study` (about 60 s,
  no gate list kept; the circuit has no `INFO_TAG`s, so stages are found from the Toffoli-rate profile, boundaries good to about +-3k T).

## 1. The gap in numbers

| | qubits | Toffolis (static = executed) | cost, lowest salt level | cost, worst salt seen | ratio |
|---|---:|---:|---:|---:|---:|
| ours `fixed` [M] | 890 | 391,326 | 368.43e9 | 371.56e9 (10 salts) | 65.77 |
| syed3000 [M] | 889 | 384,003 | 360.73e9 | 362.39e9 (5 salts) | 67.4 |
| e9f54be3 (public frontier) [M] | 892 | 395,586 | 374.69e9 | 377.87e9 (10 salts) | 64.7 |

* [D] Same-salt gap is 2.1%: T gives 1.87% (7,323 Toffolis), Q gives 0.22%. Everything else is zero (R = 1.1918 for all, 0 failures).
* [M] Per-salt cost has three levels in every circuit (x1, x1.0046, x1.0085), so the level is set by the verifier's salt, not the circuit.
  Syed's 5 salts never reached the top level; our 10 did. At the same level ours is 66.0 to 66.3 against his 67.4 to 67.8: the real gap is
  about 2.1%, and the headline 65.77 against 67.4 overstates it by 0.4% purely from salt sampling. Ten salts of his circuit would
  probably read about 67.2 [G].
* [D] Ours is already 4.3k T below the public frontier (395.6k) and 7.3k above syed.

## 2. Per-stage breakdown (ours measured; public from `dqi-stage2.md`)

Ours, from the Toffoli profile of `fixed.kmb` [M], boundaries estimated from rate and live-qubit changes:

| stage | instr. index | Toffolis | public tag count (e9f54be3) [M, earlier pass] |
|---|---|---:|---:|
| extract fwd | 0.41M to 5.0M | 74.9k | extract 54.5k |
| seeded synthesis fwd | 5.0M to 10.0M | 29.7k | synthesis 31.5k |
| convert fwd (`night_outer` + `projective_finish`) | 10.0M to 13.7M | 56.2k | convert 54.2k |
| scan | 13.75M to 19.05M | **45,045 = 4,095 x 11 exactly** | 44,275 = 4,025 x 11 (gauge skips 70) |
| unconvert (finish + outer closing) | 19.2M to 25.0M | 68.2k | unconvert 55.7k |
| unsynthesis | 25.0M to 31.0M | 43.5k | unsynthesis 38.3k |
| unextract | 31.0M to 39.8M | 73.6k | unextract 96.8k |
| total | 39.85M instr. (31.6M CX) | 391,326 | tagged sum 375.3k of 395,586: **20.3k untagged** |

Reading: extract+synth+unsynth+unextract is 221.7k ours against 221.2k public, matching the earlier 0.6% result. The scan matches to
the Toffoli (our 770 extra is the unused gauge). So the 7.3k to syed sits in `convert + unconvert` (ours 124.4k [M], public tags 109.9k
but with 20.3k untagged somewhere, so not comparable) and in anything syed's un-vendored final pipeline changes. Note ours is asymmetric:
unconvert is 12k above convert (public tags: 1.5k).

Qubits [M]: ids 0 to 839 are the syndromes; ids 840 to 889 (50 qubits, 24 carry plus 26 scratch/flags) are all live from 0.41M to
the end, so 890 is a flat floor, not a transient peak. The 12 qubits 852 to 863 (upper half of the carry) are touched only in extract
(0 to 5M) and unextract (30M to 40M) and are idle for 25M instructions (63% of the circuit). [R] The vendored extractor's own ledger
states `base_data_qubits=864, peak_Q=890`, so 890 is set by the extractor itself (864 + 26) and syed's 889 must come from his
composition (seed seam), not from a convert/scan trick.

[R] The extractor's source model (pair of forward and reverse, n = 35, j_min = 15): queries 99n(n-1) = 117.7k, consuming scales
99(4n-2) = 13.7k, deferred inverses 390n = 13.7k, affine phases 264n = 9.2k, tail controller 138(n-j_min)-45 = 2.7k, seed pieces
35+45+260: about 157k, i.e. 40% of T, of which the 595 GF(2^24) products (99 T each, forward and again in reverse) are 30%.

## 3. Where the 7.3k could be (ranked by how well it is supported)

1. [M/R] Gauge: 70 positions x 11 = 770 T (`mask_gauge_blocked` is Clifford only, zero quantum scratch). Known, 0.2%.
2. [M] Extract/synthesis round trip +1.4k T over the public circuit's four stages (0.36%).
3. [G] Qubit 889 vs 890: 0.22%.
4. [G] The remaining 3.9k to 5.2k T (1.0% to 1.3%) is in convert/unconvert or in the options of syed's `v7_pipeline.configure`, which
   rebinds about 15 module attributes at import time and is **not vendored** (`syed-dqi-audit.md`). Our `fixed.py` calls
   `night_outer.emit_prefix(..., fused=False)` while the module default is `fused=True` (history-fused Toeplitz finish); we never
   use that path. This is the best lead, unverified.

## 4. Design ideas, ranked

| # | idea | expected gain | effort / risk |
|---|---|---|---|
| 1 | **Close the convert/unconvert asymmetry**: add `stage=` hooks to `night_outer`, `projective_finish` and the scan call in `fixed.py`, get a native per-call Toffoli ledger of both directions, then try `fused=True` (histories `E` from the synthesis records, `X = reversed(E)+O`) and the cheaper closing orders. | 3k to 6k T = 0.8% to 1.5% [G]; the +12k forward/reverse asymmetry is [M], that it is removable is not | Medium. Needs one build with stage callbacks, which executes vendored syed kernels (our normal `--gen fixed` build on Kaggle already does; local narrow n = 70 is cheap). Risk: fused finish may need extra history words, i.e. qubits (each +1 costs 879 T). |
| 2 | **Parity items together**: enable the real mask gauge (`open_gauge`/`close_gauge` with the 70 selected positions, scan `positions` 4,025), re-seed the synthesis boundary so the 1.4k round-trip excess goes, and try `j_min` 15 to 18 or 19 (tail controller costs 138 T per slot; dqi-syed.md says the weight law has no mass below 19, so each step saves 138 T and no failures if that holds). | 770 + about 1.4k + about 400 = 2.5k T = 0.6% to 0.7% [D/G] | Low to medium. All vendored kernels; narrow n = 70 official verifier first. Risk: gauge needs the compensation phase wired and masks transformed classically; `j_min` is only safe if the weight law claim is checked on the DQI sampler. |
| 3 | **Find the 889th qubit** inside the extractor/seed seam (`rolling_tail.release_spare`, `gauge_prefix`, `scalar_seed` seam), since the extractor's own ledger says 890. | 0.22% | Low value, uncertain, medium effort (needs syed's seam to compare). Do after 1. |
| 4 | **Lower-rank GF(2^24) product**: there are about 1,330 products in the extractor pair (1,190 queries + 138 scales) plus norms; each unit of rank is 1.3k T = 0.34%. Our 99 is degree 6 over GF(16), 11 points, 9 each. Search places of mixed degree or other towers (a known rank table, e.g. for GF(2^24), not consulted here). | 99 to 95 would be 5k T = 1.3%; 99 to 90 would be 3.4% [G, depends on the literature] | Medium to high: new tensor, `phase_product`/HMR mask gadgets in `gf24_arithmetic` assume the structure. Risk that 99 is already near-optimal. |
| 5 | **Sub-quadratic extraction** (half-GCD-style recursion on the 595 query pairs: extract the first half, apply its 2x2 continuant matrix, whose evaluations at the other nodes are free CNOT maps, to the second half, so about 4 products per node instead of about 17). | Unknown: at n = 35 the first half's matrix polynomials must be synthesised (about 136 products) before use, which eats most of the saving; could be 0 to 8% [G] | High: new decoder, needs a classical prototype first (`thiele.py` is the model), reverse must also be rebuilt. Research bet, not a milestone. |

What would **beat** syed: ideas 1 + 2 + 3 together are about 2.5% to 3% [G], which equals his lead (2.1%); beating him by more than that needs
idea 4 or 5.

## 5. Not supported (ruled out or no gain found)

* Mask gauge as a big lever: [R] zero T, 770 T maximum.
* Scan: ours is exactly 4,095 x 11 [M]; 11 = 10 ladder + 1 CCZ is the AND-of-13 floor with the classical-mask phase already free.
* Extract kernel differences: it is verbatim.
* Q from the idle carry half: the 12 qubits (852 to 863) are idle in the middle stages [M], but the peak is fixed by the extractor, so lending
  them as scratch to convert/scan does not lower the maximum [D].

## 6. Measured versus guessed, in one place

Measured: all numbers in sections 1 and 2 (ledger rows 84, 91, 5, 7, 11 and the `fixed.kmb` stream), the qubit liveness of ids 840 to 889,
the scan being exactly 45,045 T, the three salt levels. Read in source (not run): the extractor ledger formulas, `fused` default,
gauge being Clifford. Guessed: every gain figure in section 4, the location of the remaining 3.9k to 5.2k T, the stage boundaries (+-3k T),
and all statements about syed's un-vendored pipeline. Not available: syed's circuit, so no like-for-like per-stage table; the first
action is to get one (fetch his dataset to `~/qcc-circuits/syed_ref/` as `HANDOFF.md` describes, run `dqi_gen.study` on it, one circuit at a time).

## 7. Update 2026-11-14: syed3000's circuit measured, and idea 1 refuted

syed3000's v12 dataset (`vqcc-own-circuit-portfolio`, Apache-2.0, provenance row S14) is now in `public/`. Both circuits were
streamed once with `dqi_gen.study` (static counts only; no third-party code run). Instruction mix:

| | ours (`fixed`) | syed3000 `dqi.kmb` |
|---|---:|---:|
| qubit ids | 890 | 889 |
| instructions | 39.85M | 52.99M |
| CCX | 372,241 | 364,619 |
| CCZ | 7,661 | 7,000 |
| CSWAP | 11,424 | 12,384 |
| Toffoli-like total | 391,326 | 384,003 |
| HMR | 75,185 | 71,531 |
| CX | 31.57M | 31.29M |
| SWAP | 529k | 379k |
| CZ | 487k | 539k |
| BIT_INVERT | 4.60M | 15.44M |
| BIT_STORE0 | 356k | 1.53M |
| PUSH/POP_CONDITION (each) | 784k | 1.52M |

The Toffoli-like totals reproduce the verifier figures exactly (391,326 and 384,003). Measured: syed3000 has 7.6k fewer
CCX, 3.7k fewer measurements and 150k fewer SWAP, and about three times the classical-bit and conditional-block traffic
(BIT_INVERT, BIT_STORE0, PUSH/POP_CONDITION), which cost no Toffolis. That points at more classically controlled
operations replacing quantum ones, but this table does not show which stage does it; that needs per-stage tags on both sides.

**Idea 1 (`fused=True`) does not work as a switch.** `fixed.py` passes `histories=()` to the vendored `night_outer`
(history-free design). The kernel's `fused` mode is the older fused finish that dots against history registers, so with no
histories it is not valid: on the `narrow` instance (full field, 71 positions) `--gen fixed` verifies (890 qubits, 346,192
Toffolis) while the same build with `fused=True` fails with 1,512 of 3,072 phase errors. Idea 1's estimate (3k to 6k T) is
withdrawn; the mismatch of 12k between our unconvert and convert remains the lead, but needs a different change.
