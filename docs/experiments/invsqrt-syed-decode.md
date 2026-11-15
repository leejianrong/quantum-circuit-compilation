# invsqrt: decoding syed3000's 46-qubit builder (QCC-13, source study)

Read-only study of the builder source in `public/syed3000__vqcc-own-circuit-portfolio/files/invsqrt_source_zip`
(Apache-2.0, `docs/PROVENANCE.md` S14). The archive was unpacked with `zipfile` into the scratchpad and only read:
nothing from it was imported, built or run. Every claim cites a path inside the archive, shortened as

* `ROOT` = `invsqrt_source/`, `N` = `ROOT/src/work/c10/narrow`, `P` = `ROOT/src/patches`, `A` = `ROOT/src/agents`,
  `E` = `N/checkpoint002/cleanroom/baseline_stage97/engine`.

Tags: **[V]** verified from source text, **[I]** inferred or estimated by us. Our code: `src/invsqrt_gen/`; our decode of
the circuit itself (dynamic, earlier): `docs/experiments/invsqrt-sqrt-division.md`. Target: 46 qubits, 1,511.5703125
Toffolis, 1 T, 33 rotations, cost 80,162.76.

## 0. Findings that change our plan

1. **The "consuming multiplier" is not a mystery.** The product is ten signed-digit rows into a 16-wire word (3 seed
   wires, 3 sign copies, the 10 `h` wires). Row i is controlled by `h_i`; it adds a rounded, shifted copy of the
   coefficient into the lower `6+i` wires of the word, and the control wire `h_i` then simply becomes the next top wire of
   the accumulator that rows `i+1..` add into. Nothing is dropped and no low column is measured. The only information
   cost is that the inverse needs the coefficient again, which is why the table is loaded twice **[V]**
   (`N/native/candidate01/lifecycle.py:241-266`, seed at `:163-172`). Our "dead end" section in
   `invsqrt-sqrt-division.md` assumed a dropped-column problem that the real design does not have.
2. **There is no one-wire endpoint.** The 25 quotient sign wires (13 history owners plus the 12 live remainder
   wires) plus a known-one wire form a 26-position word that is rotated in place. A cyclic CSWAP network
   controlled by affine functions of the four exponent flags realises the `2^k` scaling, and 33 `Z_POW` rotations act on the
   word wires (26 ring positions, 7 overflow features); 3 more overflow angles are Clifford or T class **[V]**
   (`N/native/candidate01/divider.py:290-328`, ring math `E/cyclic_phase.py:1-14`, oracle
   `N/native/candidate07/oracle50.py:30-47`).
3. **Q48 to Q46 is worth 4.2% of the cost, the Toffoli changes only 2.0%** **[V arithmetic]**: candidate10 (Q48,
   1,548.75 Toffolis, 85,468.7) becomes Q46 (1,511.57) by loader re-synthesis and width patches. 46/48 times 85,468.7 is 81,909;
   the Toffoli change gives about -1,710 and 4 T to 1 T about -35, landing on 80,163.
4. **Much of the Toffoli saving of the last stretch is spare-wire trading**, not new arithmetic: held CSWAP pairs in the
   endpoint, rebuilt-on-demand root bits, and a mechanical post-pass scan over all 3,133,452 inputs (section 1.3).
5. **The table was co-designed once, not to the end.** The fit maximises the accuracy margin and makes one slope bit
   implicit (a quadratic function of the address); the other bits are plain fitted values that a separate search then
   synthesises (`N/research/recompute_root/models/phasefit_z1_K7_G4_m37_virtual_quadS2_36_12c0.json`, keys
   `objective`, `coefficient_encoding`, `implicit_slope_bit`) **[V]**. Idea 2 in section 4 builds on that.

## 1. Pipeline and stage list

### 1.1 Entry point

`ROOT/README.md:14` states Q = 46, 1511.5703125 Toffoli-like gates, 1 T, 33 generic rotations (computed, not sampled);
output sha256 `321aff83...`. `ROOT/build.sh` (checks the host `kickmix.so` and verifier hashes, `:34-60`) then:

1. `tools/build_variant.py` loads a hash-pinned base generator (`N/arithmetic_round2/native/candidate10/generate.py`,
   "candidate10", the Q48 arithmetic composition) and applies the 13 patch modules of `P/PATCH_ORDER.txt:1-13`, `Q 46` at `:16`.
   Patches replace functions on live module objects; no pinned file is edited (`build.sh:107-113`,
   `ROOT/src/tools/build_variant.py` docstring).
2. `tools/pipeline.sh` (34 lines) runs mechanical passes on the circuit text, each driven by a full-domain scan of all
   3,133,452 inputs, then compiles and runs the exact all-HMR-transcript proof: (a) `audit_affine` finds Toffoli-like gates whose
   product is an affine function of live wires and rewrites them to CX or measure-and-CZ; (b) `audit_pairs` +
   `hold_pass` hold a recomputed AND product on a spare wire; (c) `merge_zpow` sums angles of `Z_POW` gates that act on the same
   Boolean feature (folds T gates into generic rotations); `ROOT/src/tools/*.py` docstrings, `pipeline.sh:15-31`.
3. `agents/composer/post_inplace.sh` runs `agents/micro47/scripts/relocate_cs2.py`, which moves a small-x correction
   into four Clifford phases in the normaliser (-1 Toffoli, -2 T), then recompiles and re-proves (`relocate_cs2.py:1-15`).
4. The sha256 is checked. (Observation: `PATCH_ORDER.txt:14` names `patch_endpoint_walk8.py` after `with`; it is not in the
   archive, and `build.sh:107-108` only acts on `patch` and `post` lines. The endpoint comes from `patch_endpoint_v9e2.py`
   plus `A/composer/p/w2core_e2.py`.)

### 1.2 The mathematics the stages implement **[V]**

`N/native/candidate01/whole_model.py:16-53` (independent integer model, after `N/native/candidate07/oracle50.py`):

* normalise: `n = x 4^k`, leading one found from the pair structure, `k` in 0..10 in 4 flags;
* `Q = isqrt(16 n)`, `v = Q - 4096` (12 bits), divisor `d = 2Q + 1`, residual `h = ((64 n - d^2) >> 6)` (10 signed bits);
* coefficient `C[v]` (14-bit, about `2^14 (4096/Q)^2`, stored as 13-bit `D = C/2` plus the odd bit used as a parity wire),
  seed `U0` from 3 signed rounded copies of `C` selected by the 3-bit class `(v(v+1)/2) mod 8` (the low four bits of the
  residual are a function of the root, so only 3 metadata bits are kept);
* `U = U0 - F/2`, `F = sum_{i<10} (2 q_i - 1) round(C / 2^(8-i))` with `q = h + 512`: the signed-digit product;
* division: remainder starts at `4096 - d`; rows `j = 9..35`, each `r <- 2r +- d (+ bit of U)`; the sign is the quotient bit,
  U's 15 bits are streamed in as dividend digits for `j <= 23`, later rows use a short analytic continuation;
  phase = `-sum sign_j 2^(37-j)` turns, scaled by `2^k` through the ring rotation.

Table: 128 rows by 16 output bits (13 coefficient plus 3 metadata), same table used in two loads.

### 1.3 Stages with Toffoli counts and live widths

Q48 column: candidate10's own ledger, `N/arithmetic_round2/native/candidate10/COMPLETE_GATE.json` (`components_expected_Toffolis`
lines 15-25, `peak_ledger` from line ~40; sums to 1,548.75 **[V]**). Q46 column: from the patch docstrings and the two
loader certificates; the final per-stage numbers are not in the archive, so deltas marked [I] are our reading.

| # | Stage (order in `emit_body`, `P/patch_w47_body.py:206-340`) | Toffolis Q48 | Q46 | live width at Q48 | Q46 note |
|---|---|---:|---|---:|---|
| 1 | Pair normalisation: 18 prefix ANDs, 34 CSWAP (two lanes, odd lane zero-supported), flags k | 94.75 round trip (51.5 fwd + 43.25 inv) | `patch_fwd_narrow` rewrites the forward only; x21 turned into a prefix in place, odd prefixes measured early [V] | 46 | stays 46 |
| 2 | Consuming root, 12 digit pairs, `v` 12 + `h` 10 (the 22 input wires) | 192 (96 + 96, RN3 saving 6) | unchanged | 39 | |
| 3 | First loader of the 128-row table onto 16 wires; raw address kept (7 slots fixed) | 61 | **56**, work cap 20, 26 + 20 = 46 [V] (`A/loader2/certs/first_cap20_56b8.json`) | 48 | |
| 4 | Metadata `H3` (from `A`,`H2`, raw a5, a6), `a6` retired at once; `H4`; 5 signed coefficient rows (7-bit add each) + overflow; first copy of rows' debts kept | 118 for coefficient (2 fwd + 1 inv) | same, `coefdisp` frees rounding carries early; `coef2_q46` +1 Toffoli to drop `D12`/rebuild from `H4` [V] | 48 | 46 [V] |
| 5 | Seed: 3 rows from the root class, `v0,v1,v3` frame; cleanup 4.5 | 17.5 total | unchanged | | |
| 6 | Consuming signed-digit product, 10 rows, word16 | 228.5 (about 103 + 125) | unchanged count; `proddisp` frees carries of rows 0-7 [V] | 48 | `a6` kept retired through it |
| 7 | `D` (13 wires) X-measured away (debts kept classical) | 0 | | 31 | |
| 8 | Divider: direct `u12` init (24 CCX, retires P13,P14), rows j = 12..24 feed from `P`, rows 25..35 tail; remainder 14 wires, sign history 13 | 578 (270 fwd + 308 back incl. history retire, 13 conditional regenerations) | `patch_hret_sat_s15k7a` retires history signs 13..15 and rebuilds them from root bits by SAT-minimal AND programs [V] | 43 + carries = 48 | 46 |
| 9 | Phase endpoint: ring word 26 (+1), CSWAP stages, 33 rotations, 4 T | 139 (+ rotation charge 230.848, T charge 1) | `w2core_e2`: pairs of CSWAP replaced by hold/measure-release (1 Toffoli instead of 2): 12 E-holds + 13 F-holds + 4 R2 holds; roots `v9,v10,v11` retired as spare lanes [V] | 48 | 46 |
| 10 | Second loader (R frame first; 4 raw address wires become work) | 79 | **70**, cap 19, 27 + 19 = 46 [V] (`A/loader2/certs/second_cap19_70nb1.json`) | 48 | |
| 11 | Second coefficient, merged transcripts, product inverse, seed inverse, then root decoder (5 values), snapshot cleanup, shared table cleanup | in 118/228.5/17.5 above; decoder 21, metadata 7, R frames 4, cleanup 9 | `seedinv` retires `v0,v1,v3` through the product inverse (41 data owners); `h2ret` retires `H2` (+3); donor T1 (3 CCX) and T2 (20 CCX) for late metadata and decoder capture [V] | 48 | 46 |
| 12 | Root and normaliser inverses | in rows 1, 2 | | 26 body | |
| 13 | Mechanical passes + `relocate_cs2` | 0 | about -23 net after the patch costs [I] | | |

The Q46 total 1,511.57 is **[V]** (`ROOT/README.md:14`). Reconciliation **[I]**: 1,548.75 - 14 (loaders) = 1,534.75; the patches
(`coef2` +1, `h2ret` +3, A6 rebuild +1, `v9` forms +4 and `v10` -1, hret rebuilds, donor tails -1 and +3) add a few; the endpoint holds
(about 29 pairs) remove about 29; the audit passes and `relocate_cs2` (-1) remove the rest. The rotation charge did not change
(1,511.57 + 0.25 + 230.848 = 1,742.67; 46 times that is 80,162.7).

Width detail at Q48 (`peak_ledger`): normalisation 22+4+20 scratch = 46; root 39; first loader and first coefficient 48
(root 12, residual 10, flags 4, D 13, H 3 to 5, snapshot 1); product forward root 12 + word 16 + flags 4 + D 13 + 3 = 48;
divider/endpoint root 12 + remainder 14 + history 13 + flags 4 + carries = 48; second loader retained root 8 + product 15 + flags 4
+ D 13 + H 3 + 5; inverse product after retiring `v3`: 6 + 16 + 4 + 13 + 3 + 1 + 5 = 48. At Q46 every one of these stages binds
simultaneously (patch comments name 46 as the cap in loaders, coefficient, product, divider cleanup, endpoint). That is why Q45 is
not a single trick.

Table of stage widths at the cuts that matter: the body is 26 wires (root 12, residual 10, flags 4); the divider holds 31 + 14 - 2 = 43
(`divider.py:149-186`); the endpoint holds 43 + the known-one wire, `p`, `c`, a threshold and a feature helper = 48 before retirements
(`N/research/combined_q48_ring26/PLAN.md`, `Q48_COMPLETE_PAPER_GATE.md` lines for the compact endpoint).

## 2. What our `src/invsqrt_gen` has and what is missing

| Stage of his design | Ours | Status |
|---|---|---|
| Deferred-phase adder, two alternating carry wires, debts paid in the mirror, split blocks | `defadd.py` (`fd_add`, `md_add`) | have, verified. His version also has conditional regeneration of the first carry (0.5 Toffoli each, 13 in the divider, 8 in the product), which we lack (`N/research/disposable_feed_carry/REPORT.md`) |
| Recorder with automatic inverse | `rec.py` | have; his generator edits function tables on live modules, ours is a recorded program, fine |
| Normalise by even shifts | `sqrtdiv_stages.normalise_even` (84 fwd) | have a plain version. Missing: direct pair map, 18 prefix ANDs, measured prefixes with Clifford repair, shared cubic correction (94.75 round trip vs our about 168) |
| Consuming square root in place | `sqrtdiv_build.sqrt_root` (102 + 14 for `R -> t`) | have the digit recurrence. Missing: signed 10-bit residual with only 3 metadata bits (we keep 14-bit `t`), tail-pair known-zero saving, carry/residual shortcuts (192 round trip vs about 232) |
| Table as 128 rows by 16 outputs, loaded twice, measured away between | `load_table` (unary iteration, 126) | have the unary version. Missing: the whole loader synthesis (below), `TableDebts` flush, the metadata bits |
| Coefficient from `A`, 5 signed rows plus overflow | `refine_d` (about 100) | partly; his rows add into a 7-wire `D` window with metadata `H3`,`H4` as sources |
| Seed from the root class | none (a constant offset only) | missing, small |
| Signed-digit consuming product, 16-wire word | `product_pm1` (separate `P`, 239 executed) | have signed-digit rows (V2), missing the consuming layout (control wire joins the accumulator) which is the 14-wire saving |
| Consuming division, quotient digits in wires freed by the remainder, history owners | `divide_rows` (364, separate window) | have the idea in prose and the `md_add` gadget; missing the direct `u12` initialiser, feed carry as a 4-variable quadratic, history retirement |
| Quotient into rotations | barrel phase (about 300 for three calls) | missing the ring: cyclic CSWAP rotation with flag-affine controls, per-position fitted angles, 7 overflow features |
| Width patches (13) | none | missing; these are the stretch from Q48 to Q46 |
| Mechanical passes on circuit text | none | missing, and portable to E023 |

### Ordered build list (own code, each step verified against an integer model in the simulator before the next)

Estimates are Toffoli changes against our V2 (90 qubits, 2,780 executed), by stage, and what each unlocks.

1. **Port the integer model**: refit our own coefficient table in his structure (128 rows, `A` 13 bits, 3 metadata bits,
   per-row slope, seed), our own linear program for angles on the ring (our `angles.py`/`joint.py` have the machinery),
   and write `phase_units`-style oracle over all 3,133,452 inputs. Needs the accuracy margin of about 3% of tolerance, so the fit
   objective is margin first. Deliverable: model passes the verifier tolerance (exact integers, no circuit).
2. **Direct pair normaliser** (forward 51.5, inverse 43.25): about -70 over ours; width 46.
3. **Consuming root with signed residual** (96 per direction): about -40; body becomes 26 wires.
4. **Table loaders and coefficient rows**: first write the unary version on 16 wires, then the product-bank loader (section 4
   idea 2); the loader search tool (heuristic search plus exact replay on 128 rows) is the biggest piece of new code. About -150 for
   lookup plus refinement.
5. **Seed and consuming product** (10 rows into the 16-wire word, control wire joins the accumulator, rounding carry from the coefficient
   bits and the control): about -250 Toffolis and about -30 wires at the product stage.
6. **Consuming divider** (direct `u12`, feed rows, tail rows, history owners, conditional carry regeneration): about -95 forward, then the
   history-retired cleanup.
7. **Ring endpoint** (CSWAP stages, 26+1 word, 33 rotations): about -150 against our barrel; angles from step 1.
8. **Second load, product/coefficient inverse, decoder, table cleanup (9 Toffolis, one universal flush of every discarded table
   function), a6/H2/v3 retirements**: this is the Q48 shape. Reaching about 1,549 Toffolis at 48 qubits is the first milestone
   (about 85.5k, ratio 24.3).
9. **Q46 patches in his order**: loaders at caps 20 and 19, coefficient/product carry release, history sign retirement with exact
   AND programs, endpoint holds, then the audit passes. A SAT-minimal AND-program tool (`tools/minand_sat.py`, not in the archive) is needed
   for the root-bit rebuilds; we have no SAT solver dependency, so write a small exhaustive search.
10. **Mechanical passes** (full-domain affine-product audit, hold pass, Z-power merge): independent, can start now on E023.

Order of risk: steps 5, 4 and 9 carry most of the unknowns.

## 3. His research history

Sources: plans and receipts under `N/` (only partly included; `RESUME.md`, `CLOSED_ROUTES_NARROW.md` are not in the archive).

* **Earlier line (Fourier/curvature, up to 57 qubits)**: `N/checkpoint002/cleanroom/baseline_stage97/engine/*` (about 110 modules)
  and `N/arithmetic_round2/inputs/fa004_v6/fa004/reports/FA004-v6_report.md`: stage97 Q56 92,279, FA003 Q57 91,882, FA004-v6 Q57 89,799
  (1,259.7 Toffolis, 14 T, 43 rotations, loading 266, uncompute 427). Its engine supplies the primitives still used
  (`paired_arithmetic.py` = deferred-phase adder, `quadratic_terms.py`, `codebook.py`, `cyclic_phase.py` = ring rotation).
* **Pivot to square root and division** ("narrow" candidates, each frozen and re-proved): candidate01 own Q49 divider and `u12`;
  candidate04 exact 50-bit angle refit (Q49, 1,562.5, 88,276; `native/candidate04/PLAN.md`); candidate05 two fewer controlled swaps
  (1,560.5, 88,178; `native/candidate05/PLAN.md`); candidate06 Q48 lifecycle (1,591, 87,842; `native/candidate06/PLAN.md`);
  candidate07 ring26 phase and 79-Toffoli second loader (1,584, 87,161; `research/combined_q48_ring26/PLAN.md`);
  candidate09/10 arithmetic composition (1,548.75, 85,469; `arithmetic_round2/native/candidate10/README.md`); then the Q47 and Q46 width
  agents (`A/width`, `A/loader2`, `A/composer`, `A/micro47`, `A/normroot`, prodcoef and prodcoef2) to 80,163.
* **Accepted gains in the Q48 stretch** (all with native all-input proofs): normalisation 97.5 to 94.75, root 198 to 192 (RN3),
  divider 587.5 to 578 (history12 retirement, `native_ar004/RESULT.md`), product 240.5 to 228.5 (V3 seed retirement, top transfer),
  coefficient 123 to 118.
* **Tried and closed (stated in the files)**:
  * conditional-normalisation gates fail cost at Q49 to Q52 (`research/lifecycle_schedule/post008_gate_v3.json`, status
    `CONDITIONAL_NORMALIZATION_GATE_ALSO_FAILS_COST`);
  * disposable feed carries: cost-neutral at Q49 and above, saving 6.5 at Q48 and 19.5 at Q47 (`research/disposable_feed_carry/REPORT.md`);
  * compact endpoint allocations that need one more wire than the cap are `PAPER_BLOCKED` at Q44 to Q50 (`research/stream_phase/alias_ring/*.json`);
  * the unchanged endpoint source cannot fit Q47/Q48 (disposable-carry report, last paragraph); the w2core version was written for that;
  * two other angle alternatives were more expensive than candidate04's (`native/candidate05/PLAN.md`, first paragraph);
  * unrestricted root/product domain claims are explicitly not made (only the real model on x = 1..3,133,452; `native_ar004/RESULT.md`).
* **Open (named but not done in the archive)**: RN4, a combined normalise-and-root streamed chart (`.../root_normalization/PLAN.md`
  "RN4"); a Q47 complete gate was never marked complete (`complete_Q47_gate false` in both loader certificates); the Q45 cases do not
  appear anywhere; the 82,740 stretch target in his plans needed 92 more equivalents than the arithmetic branches gave
  (`N/arithmetic_round2/research/root_normalization/PLAN.md` "Fixed complete ledger").
* **Method worth copying**: every component is priced first as a paper gate with exact ownership cuts, then proved on all inputs and all
  measurement transcripts before composition; nothing is tuned against sampled runs.

## 4. Ideas to beat 80,162.76, ranked

Cost lever sizes (at the final point, E = 1,742.67): one qubit = 37.9 Toffoli equivalents = 2.17%; one Toffoli = 0.057%; one rotation
site is about 7.0 equivalents = 0.40%. A bit of rotation precision is only 0.56 T per site, so 1 bit of arithmetic margin is worth about
4.6 equivalents.

| Rank | Idea | Gain | Risk | Evidence |
|---|---|---|---|---|
| 1 | **Q45**: pack `h0` into the flag code space (code 12..15), first loader at cap 20 then needs 25 + 20 = 45; second loader to cap 18; retire one more root bit through the product, coefficient, divider and endpoint | gross -2.17%; patches +10 to +25 Toffolis (0.6 to 1.4%); net about -0.8 to -1.5% | high: every stage binds at 46 at once | [V] pack and unpack code exists and was dropped only because cap 20 fit (`patch_w47_body.py:42,56-90`); the first loader certificate says 25 other owners once packed (`A/loader2/certs/first_cap20_56b8.json`, header comment of `patch_ld_first20_56b8.py`); [I] the rest |
| 2 | **Loader and coefficient co-design**: choose more table bits (beyond the implicit slope bit) as low-rank functions within the accuracy margin, so the 16-output load (56 and 70 ANDs) and the 118 coefficient Toffolis shrink | -10 to -20 Toffolis (0.6 to 1.2%) | medium: the margin left is only about 2.7% of tolerance (worst error/tolerance 0.9736) | [V] fit objective is margin and only the slope bit is implicit; [V] the search is heuristic and many runs hit `TIME_LIMIT` (54 results); [I] gain |
| 3 | **Mechanical passes on our own circuits**: affine-product audit, held recomputed products, Z-power merge, constant propagation of dead controls (our provenance row on the hirokikanotmc notebook is the same family) | -1% to -3% on E023-class circuits; 0.5% on a Q46 clone | low, independent, tooling only | [V] pass design in `tools/*.py`; [I] gain on ours |
| 4 | **Fuse normalisation and root** (his RN4, never built): stream the normalised pairs into the root recurrence so the 20 prefix wires and 34 swaps shrink | -20 to -40 Toffolis (1 to 2%) | high: new chart, new phase obligations | [V] listed open (`.../root_normalization/PLAN.md`); [I] size |
| 5 | **Table rows / digits**: K6 (64 rows) with a fourth coefficient row, or drop the last tail rows of the divider by absorbing them into one analytic constant, paid for by the accuracy freed in 2 | -5 to -15 Toffolis | high: error budget is 97% used | [I] only |
| 6 | **More spare-wire holds in the endpoint and divider** where a stage has a free wire at Q46 (hold a recomputed AND on the spare wire instead of paying it again) | -3 to -10 Toffolis | low to medium; only valid where width is not already binding | [V] mechanism (`hold_pass.py`, `w2core_e2.py:281-304`); [I] sites |
| 7 | **Angle sites**: try to zero more ring or feature sites with the exact 50-bit program, as `global_zero33` did for one site | 7 equivalents per site (0.4%) | high: 2.7% margin | [V] one site was zeroed; [I] for more |
| 8 | **Smaller second table**: only the 13 bits that `D` needs in the undo, not 16 outputs | -5 to -10 Toffolis | medium: metadata bits are needed by the coefficient inverse | [I] |
| 9 | **Rounding choices**: centred constants, carry-in rounding bits on each product row, per-row biases, quantised angles on the 2^-50 grid; his are already exact-fitted | under 0.3% | low | [V] angles fitted by exact screen (`research/postgate_angle_refit`); [I] |

Not recommended (derived, no evidence it helps): multiplying by a table of 1/s instead of dividing (needs a 13 by 12 multiplier,
about 150 Toffolis); replacing mirror uncompute of the divider by measurement (the digit functions are not low-degree).

## 5. Provenance rows to add (idea, source, what we will rewrite)

For `docs/PROVENANCE.md`, all from static reading of `invsqrt_source_zip` (S14, Apache-2.0), nothing executed:

| Idea | Source | What we will rewrite |
|---|---|---|
| Product rows controlled by the multiplier bits, each control wire joining the accumulator after its row; rounded, shifted coefficient with the rounding carry from the coefficient bits; seed from three rows selected by the root class | `N/native/candidate01/lifecycle.py:163-266` | consuming product and seed stages in `sqrtdiv_stages.py` (new) |
| Quotient signs held as the 26-position ring, rotated by cyclic CSWAP stages with flag-affine controls, per-position fitted angles, overflow features on `AND(bit, k > j)` | `divider.py:290-328`, `E/cyclic_phase.py`, `candidate07/oracle50.py` | new endpoint replacing `barrel_phase`; our own angle fit |
| Direct pair normaliser with measured prefixes and shared cubic correction | `N/arithmetic_round2/research/root_normalization/*PLAN.md`, `P/patch_fwd_narrow.py` docstring | new `normalise_pair` stage |
| Table loaded twice with every discarded function recorded as a debt and repaid in one flush (about 9 Toffolis) | `A/loader2/certs/*.json` notes, `P/q46_loaders.py` | `TableDebts`-style ledger and loader emitter |
| Root bit retirement by X-measurement with deferred repayment by Z on an exactly rebuilt wire; SAT-minimal AND programs | `A/composer/p/w2core_e2.py:410-440`, `P/patch_seedinv.py`, `P/patch_h2ret.py` | retire/rebuild helper plus a small exhaustive AND-program search |
| Hold a recomputed AND on a spare wire; release by measurement and CZ | `ROOT/src/tools/hold_pass.py`, `w2core_e2.py:281-304` | circuit-text pass over our own circuits |
| Affine-product audit and Z-power merging over the full input domain | `ROOT/src/tools/audit_affine.py`, `merge_zpow.py` | own scanner on the kickmix simulator |

Licence note: the archive carries Apache-2.0 and a NOTICE; code is to be written fresh, so only these ideas enter our tree.
