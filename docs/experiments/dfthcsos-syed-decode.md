# dfthcsos: decoding syed3000's 11.31x circuit, and whether to start from his table (QCC-16, QCC-15)

Read-only study plus cost-model evaluation. Nothing from his archive was imported or run: the zip was extracted to a scratch
directory, his code was read with Read/grep only, and `submission.npz` was loaded as data (numpy, `allow_pickle=False`) and
scored with the competition's own `evaluate_words` and with our `src/dfthcsos_model`. No circuit was built or verified.
Licence of the archive: Apache-2.0 (`LICENSE`, `NOTICE` in the zip); copyright 2026 Syed Asad Ali.

Tags: **[V]** read from his source (cited as `file:line`, paths relative to `dfthcsos_source/` in the zip), **[M]** measured by
me with our code on his data, **[I]** inference. Scratch scripts (not committed) are in the session scratchpad
(`.../scratchpad/scripts/`: `eval_syed.py`, `plans_check.py`, `analyse_words.py`, `relsupport.py`, `scen.py`, `wide.py`,
`ours_now.py`, `lam.py`, `helper.py`); they can be turned into one `scripts/dfthcsos_syed_decode.py` on request.

## Verdicts

1. The table is **output only**. The archive ships the polish and the loader compiler, not the continuous fit that produced
   the vectors. We can reuse the table (words, weights, plans) but not regenerate its basin from his code.
2. Of the 14,810 Toffolis, 8,148 (55.0%) are angle loaders. Inside the loaders, 72% are product Toffolis (2,945 of 4,074 per
   pass), 25% are high-address monomial ANDs (1,034), 2% low ANDs (90); 5 more sit in circuit 0. His loaders sit at the counting bound of their architecture for 7
   of 15 circuits (189 products against a bound of 188).
3. **Our loader code can already load his table**, today, with no change except J = 4: the cost model gives **9.06x**
   (against 2.50x for E040). With a small helper-line change about **10.0x**, and with his product plans (as data) **11.31x**,
   which is a match, not a win. A bigger step needs a new cut search, which we do not have.
4. To beat 11.31 from his table, the only levers with real headroom are structural (wider circuits at a different address
   split, recoding the early batches). Weights-only refit is exhausted, 7 bits is ruled out. Own-basin routes top out near 8x.

## 1. How the table was produced

### What is in the archive [V]

| part | content | status |
|---|---|---|
| `submission.npz` | `U` (8, 143, 76), `W` (8, 143, 44), `H2_I` (8, 44), `tree_edges` (75, 2), `angle_words` (1220, 75), `H1_I`, `Hsym_lower` | data, "came out of long fitting and search runs" (`README.md:14`) |
| `plans/angle_k_0..14.json` | per-circuit frozen plan: `explicit_products` (l1, l2, out), certificate, padding rows | data |
| `compiler/` (11 files) | emit a circuit from (plan, words); matroid-parity matching; padding; helper separation | runnable build (`README.md:13`: "No search or optimisation is rerun") |
| `research/scripts/` (54 files) | metric model, weight refits, word-move polish, cut planners | "do not run from here" (`research/README.md`): inputs such as `inputs/chem_goal_v18/...`, `inputs/chem_pack/v14` are not shipped |
| `verification/prove_loader_branches.py` | exact all-branch proof of each loader | proves each loader only on its two legal endpoints (word batch k-1 and batch k) (`README.md:90-91`) |

The fit is absent. [V] No file in `research/` or `compiler/` contains an optimiser over the vectors `U` (grep for torch, jax,
adam: no hit). The research scripts all start from an existing package: `pipeline.py:13` and `homotopy.py:15` load
`inputs/chem_goal_v18/deliverables/six_cache_words_combined_v18/submission.npz`; `compiler/gauge_plan_fit.py:22` loads
`input/chem_pack/v14/submission.npz`. `manifest.json:90` calls the compiler "inherited from accepted package C". So the
chain is: an earlier package (v14, then v18 "six-cache words") whose origin is not in the zip, then the D35 polish.
The vectors in `submission.npz` are the end of a fit we cannot see; the table was produced by:

- weight refits with the vectors frozen: `refit.py`, `alfit.py` (augmented Lagrangian, minimise lambda_eff subject to
  error_1, error_2 <= target and E_gap >= floor + margin, `w = p - n` so the L1 part is smooth), `exact_refit2.py`,
  `repair.py`, `sqp.py` [V: file docstrings]; one-body rows re-rounded by `onebody.py`;
- code-preserving word moves priced exactly by a fast metric model (`fastchem.py`: Gram-matrix form of error_2), applied
  one at a time (`word_greedy.py`, `word_pairs.py`, `word_polish.py`, steps of 8, 16, 32 on the high bits, bits 0 to 2 and the
  helper kept), then a weight refit; `parity_code.py` decodes the bit-1 parity code exactly by enumerating the 2^11
  nonlinear low parts; [V]
- loader planners that search for the cuts (`minrank.py`, `planner.py`, `prefix_*.py`, `compile_*.py`, `climb147.py`).

### Parameters and quality, with our cost model [M]

`eval_syed.py`: official `evaluate_words(inp, angle_words, tree_edges, 8)` on his npz, then
`dfthcsos_model.score((8,143,44), Angles(8148, 128, J=5, brot=8), Lambda, E_gap)`.

| quantity | value | unit | gate |
|---|---:|---|---:|
| R, B, C | 8, 143, 44 | - | - |
| addresses A = 76 + R B | 1,220 | words | - |
| word columns | 75 (15 batches of J = 5) | words per address | - |
| bits per word (brot) | 8 | bits | - |
| error_1 | 0.019610 | Ha | 0.02 |
| error_2 | 0.0199988 | Ha | 0.02 |
| E_gap | 3.9148982 | Ha | > 3.914898 |
| Lambda | 282.974 | Ha | > 49 |
| lambda_eff | 46.9073 | Ha | - |
| T_total | 14,810 | Toffoli | - |
| Q_total | 427 | qubits | - |
| cost | 296,635,967.5936 | - | - |
| ratio vs baseline 3,355,599,588.3 | 11.312 | x | - |

The model reproduces his stated cost to every printed digit (296,635,967.5935997). [M] The tree is not a path or a heap: it is
a hypercube-like tree of depth at most 6 (mean depth 2.95; `[[0,1],[1,3],[1,5],[1,9],[5,13],[0,2],...]`). [M]

Where T_total and Q_total go [M]:

| term | value | share of T_total | note |
|---|---:|---:|---|
| angle loaders (both passes) | 8,148 | 55.0% | 15 circuits, 4,074 per pass |
| inner state prep (QROAM, k = 4) | 4,095 | 27.7% | fixed by shape and brot |
| Givens | 2,250 | 15.2% | 2 (N-1)(2 brot - 1) |
| outer state prep | 317 | 2.1% | |
| persistent prep qubits | 84 | 19.7% of Q | |
| word registers | 40 | 9.4% of Q | J x brot |
| inner QROAM temporaries | 303 | 71.0% of Q | the loaders' own scratch (77) is not binding |

Lambda and weights [M] (`lam.py`): Lambda = 282.97 splits into the two-body part 269.42 (95.2%) and the one-body part 13.55
(4.8%). The two-body part, 0.25 sum (S + T)^2 with `S` the per-copy L1 norm of `w` and `T = |W + sum w|`, is 130.7 (S^2/4)
+ 112.6 (S T / 2) + 26.1 (T^2/4). Comparison with our fits (same convention, `w` as stored):

| fit | shape | median S per (rho, c) | sum S^2 / 4 | sum abs(w) | exact zeros in w |
|---|---|---:|---:|---:|---:|
| syed3000 D35 | (8, 143, 44) | 1.12 | 130.7 | 411 | 18.0% |
| ours fit-b | (8, 143, 44) | 2.46 | 644.9 | 917 | 0% |
| ours fit-e (exact) | (8, 176, 56) | 2.22 | 598.0 | 1,015 | 0% |

So the Lambda gap (283 against 490 to 560) is a gap in the weights: his are 2.2x smaller in L1 per copy and 18% exactly zero.
Whether that is the vectors (basin) or the weight objective (his `alfit.py` constrains error and minimises lambda_eff; ours
penalises) is not decided by this data: see item 7 in section 4. [I]

### The table carries codes that the loader exploits [M]

`relsupport.py`, `plans_check.py`: for batch k, delta_k is the XOR of word batch k and k-1 per address (40 output bits).
Take its algebraic normal form over the 7 high and 4 low address bits. The span of the coefficient vectors of the
terms that are nonlinear in the low bits has dimension `nl_rank` out of 35 usable outputs; the null space is the set of
output relations the loader gets for free.

| circuits | nl_rank (of 35) | relations | what they are |
|---|---:|---|---|
| k = 0 to 3 | 35 | none beyond the helper | |
| k = 4 to 7 | 30 | 5 | bit 0 of each of the five words has no nonlinear low part (an LSB code) |
| k = 8 to 14 | 29 | 6 | the same five LSB codes, plus the XOR of bit 1 over the five words (a parity code) |

The helper: for every word of every batch, bit 7 XOR bit 6 equals a pure function of the four low address bits, the same for
all 15 batches, a single monomial per slot: low monomials 3, 5, 6, 9, 10 (l0 l1, l0 l2, l1 l2, l0 l3, l1 l3) for the five
slots (density 25%, so 25% of words are not in the half circle). [M, `helper.py`] The earlier note's "almost always 0" in
`dfthcsos-stage2.md` is wrong. In his code this is the "helper" `emit_plan.py:52` and the separation check
`helper_coordinates.py:6-13`. Because rotating by +pi flips bit 7 only and negates the decoded vector, which the objective
(`u u^T`) does not see, the helper is a free gauge choice per edge with the sign carried up the tree, the same device as our
`post.angles_of(half=True)`. [I]

## 2. Plans and compiler: where the Toffolis of the loaders go

### The architecture, in my own words [V: `compiler/emit_plan.py`]

One circuit loads the delta between two consecutive batches of five 8-bit words, addressed by 11 selection qubits split
as 7 high and 4 low bits. Everything is built from monomials of the address bits.

- High lines: all 76 nonzero monomials of the 7 high bits; the degree-1 ones are the selection qubits, the 69 of degree >= 2
  each cost one AND (`emit_plan.py:72-75`), uncomputed by measurement and a conditional CZ (`:134-136`).
- Low lines: the 15 low monomials. The four degree-1 ones are selection qubits. Five come free because the old word registers,
  after `CX bit6 -> bit7`, already hold the helper functions (`:64`, `:76-84`; both the old and the new words must have the
  same helper table, asserted at `:56-57`, which is legal only because the circuit has to be right just on those two
  endpoints). The other six cost an AND (`low_helper_cache.py:2,41`: exactly six extra ANDs). The high part of the helper is
  cancelled by CX from high lines (`:76-78`).
- Planes: 7 per word, 35 in all; the eighth bit is bit 6 plus the helper (`:52`, `:65`).
- Products: a Toffoli computes `(l1 + h1)(l2 + h2)`, two rank-one terms at once, with `l` a form over low lines and `h` a form
  over high lines; the result is fanned out by CX to an output mask over the 35 planes before and after the Toffoli
  (`:97-110`). Its cross part is `out (x) (l1 (x) h2 + l2 (x) h1)`. The pure-high and pure-low leftovers are CNOT-only (`:111-133`).
- Choosing the products is a linear matroid parity problem: columns `l (x) out` (525 = 15 x 35 coordinates), cuts that
  restrict candidates to the span `W` of the plan, a randomized alternating matrix over GF(2^8) as witness, columns chosen
  and checked independent over GF(2) (`extract_matching.py:36-88`, `parity_recover.py:94-112,152-162`). Toffolis of the
  products = `dim W / 2`.
- The plan is data: for each k a list of (l1, l2, out). The coordinates `h1, h2` of each product are recomputed from the
  words (`emit_plan.py:41-51`), so weight-only changes keep the circuits (`rebuild.py:6`), but any word change can leave
  the span, which his `gauge_plan_fit.py:25-31` tests (`old_plan_reusable`).

### Verified on his data [M] (`plans_check.py`, my own reimplementation of the span test)

For every k, the columns of the plan are independent over GF(2) and every high-monomial cross matrix of the (padded) table lies in
their span. Products: 2,945 in total. The plan file is thus a complete certificate for the table.

| k | products (his plan) | hi ANDs | low ANDs | Toffolis per circuit (manifest) | span dim of W | cuts (of 525) | nl_rank | our per-plane planner (products) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 213 | 69 | 6 | 293 | 426 | 99 | 35 | 285 |
| 1 to 3 | 212 | 69 | 6 | 287 | 424 | 101 | 35 | 280 |
| 4 to 6 | 193 | 69 | 6 | 268 | 386 | 139 | 30 | 254, 254, 255 |
| 7 | 194 | 69 | 6 | 269 | 388 | 137 | 30 | 255 |
| 8 | 189 | 68 | 6 | 263 | 378 | 147 | 29 | 253 |
| 9 to 14 | 189 | 69 | 6 | 264 | 378 | 147 | 29 | 253, 255, 255, 255, 254, 255 |
| sum per pass | 2,945 | 1,034 | 90 | 4,074 | | | | 3,923 |

Sum check: 293 + 3 x 287 + 3 x 268 + 269 + 263 + 6 x 264 = 4,074 per pass, as the README states (`README.md`, table). The 5
Toffolis that k = 0 has above 213 + 75 and the one fewer in k = 8 (`high_cache_plan`, AND_count 68) come from their special
emitters (`emit_k0.py:17,40,95` uses windows of live low lines; `high_subspace_emitter.py`). [V/I]

Why 189: the cross matrices of the 75 high monomials give a local target space of dimension 75 in each of five blocks
(three low monomials each, `rank 75`, `full_dimension 30` in the plan certificates), so `dim W >= 5 x 75 = 375` and products
>= 188; his k >= 8 plans have `dim W` = 378. [M, from the certificates, and our own bound in `dfthcsos-stage2.md`] Each added
code relation lowers the span: 212 with the helper only, 193 with five LSB codes, 189 with the parity code.

### Against our loader families [M, `analyse_words.py`, `scen.py`]

| family | planning | products per circuit on his words (k >= 9) | notes |
|---|---|---:|---|
| ANF line basis, per-plane (`anf.py`) | independent rank factorisation per plane, `ceil(rank / 2)` each | 253 to 255 | what we have; rank per plane 4 to 15 |
| shared product (`shared.py`) | terms shared by fan-out, plan supplied | (needs a plan) | exactness only |
| matroid pairing (`matroid.py`, `parity.py`) | pairs `(l1, l2, out)`, cuts searched at random | 262 without cuts on our own 8-bit table | the cut search is the open problem |
| his plan | cuts found by rank-guided descent from full saturation plus MinRank block search | 189 | |

The difference between 254 and 189 is the cut search. The per-plane planner cannot use the output fan-out sharing at all; the
matroid code has the machinery but not the cuts. [I]

## 3. Can our loader code take his table?

Yes for loading, no for matching without more work. Estimates are cost-model scores (`scen.py`, `ours_now.py`) with his
`lambda_eff` = 46.907, shape (8, 143, 44), brot 8, and his words; no circuit was built.

| option | change to our code | angle Toffolis (both passes) | Q_total | T_total | cost | ratio | tag |
|---|---|---:|---:|---:|---:|---:|---|
| his circuits | - | 8,148 | 427 | 14,810 | 296,635,968 | 11.312 | [M] |
| our `anf` loader as it is, J = 4, lb = 4, `sign_ext=False` (19 circuits) | none | 12,192 | 419 | 18,854 | 370.6 M | 9.055 | [M] |
| same, lb = 6, J = 5 (15 circuits) | none | 14,058 | 427 | 20,720 | 415 M | 8.086 | [M] |
| per-plane planner with the helper trick, J = 5, lb = 4 | helper line trick (below) | 10,096 | 427 | 16,758 | 335.7 M | 9.997 | [M] count, [I] it fits (126 + 1 qubits) |
| relation-aware dimension bound, no block cuts | a cut search that finds the relation structure only | 9,454 | 427 | 16,116 | 322.8 M | 10.395 | [I] bound |
| his plans as explicit data, our emitter | explicit-plan adapter, padding rows, k = 0 windows | 8,148 | 427 | 14,810 | 296.6 M | 11.312 | [I] |
| bound 188 products in all 15 circuits | recode batches 0 to 7 | 7,890 | 427 | 14,552 | 291.5 M | 11.513 | [M] model, [I] reachable |

The J = 4 row needs nothing new: `build_anf_family(words, 8, 4, 4, sign_ext=False)`, 124 qubits, because J = 5 needs 132
qubits (11 + 40 + 1 + 69 + 11) and the cap is 128. The words do not have to be grouped the way his plans group them when we
use our own per-plane planner (any batching is legal, the verifier only sees the circuit sequence), but the codes then no
longer line up with the grouping, so the loader pays full price on its bits.

What we would have to change, in order of value:

1. **Helper trick** (~40 lines in `anf.py`): load planes 0 to 6 only, `CX bit6 -> bit7` before and after (our `sign_ext`
   already does this), give the bit-7 qubit the helper function (a pure low monomial plus a high part) as F + G, and reuse
   the five bit-7 qubits as free low lines (monomials 3, 5, 6, 9, 10). That saves 5 ANDs and 5 qubits per circuit and
   makes J = 5 fit under 128. Prerequisite for any table with this helper: `post.angles_of` must also produce the
   prescribed bit-7 XOR bit-6 pattern (choose theta or theta + pi per edge, sign carried up). [I]
2. **Explicit-plan input for `matroid.build_pair_loader`** (~20 lines): accept the `(l1, l2, out)` list and compute `h1, h2`
   by `matroid.coords`, instead of `plan_products` choosing pairs. Our own representation already has the same product form;
   the architecture matches his (`dfthcsos-stage2.md`, "Public loader architecture").
3. **Padding rows**: our `planes_of` zero-pads addresses 1220 to 1231; his plans carry 12 literal rows per circuit chosen so
   the target stays in the span (`padding_completion.py:11-41`); we can take them from the plan data or solve the 12 free ANF
   coefficients ourselves (`rebuild.py:20-43` shows the structure: a triangular system). [V/I]
4. **k = 0 windows**: circuit 0 schedules the low cache in four windows of live low lines (`emit_k0.py:17,40`, `k0_windows.json`),
   probably because it has no previous batch whose registers could carry helper lines [I]. Cheapest: build circuit 0 with the per-plane planner (about +67 Toffolis per pass,
   +0.5% cost) and the rest from plans. [I]
5. **Licence**: the plan JSONs are data under Apache-2.0; using them needs a notice in `THIRD_PARTY_NOTICES.md` (owner
   decision, as for S14). The plan is tied to his exact words: any word edit may leave the span. [V]

Caveats:

- All of his loaders are proven only for the two legal input endpoints (`README.md:90-91`), not for arbitrary register contents.
  The helper trick depends on that. Our loaders are correct for arbitrary inputs (delta tables), so the helper is a
  genuinely new degree of freedom for us, and a check we must reproduce with the official verifier, not just kickmix. [V/I]
- Matching 11.31 has no leaderboard value by itself: his circuits are already verified by us (ledger, S14), and 11.31 against our
  `best/` entry (91d0ad25, 11.20) moves the geometric mean by (11.31 / 11.20)^(1/3) = 1.0033. [M, arithmetic]
- The cost model counts Toffolis and qubits; nothing here is verified by the official verifier.

## 4. History, open items, and what could beat 11.31

### His history [V/M]

- Three generations of loaders are visible in the plans' `method` strings: k = 0 to 3 ("own low-basis construction with actual
  block ranks [75, 75, 75, 75, 75]"; 212 to 213 products), k = 4 to 7 ("UNQUALIFIED physics candidate; own weak-S2 relative
  cross-parity code", i.e. the five LSB codes; 193), k = 8 to 14 ("six affine and cubic bit2 code relations", prescribed cubic
  intersections; 189). Several plans came from "agent work trees" that are not shipped (`research/README.md`); the plan
  files cite their basis files (`agents/cache_savings/...`, `agents/root_recovery_prefix/...`).
- `manifest.json`: this build (D35) replaced loaders 7 and 8 and changed batch 7 relative to an earlier npz
  (`f53c8c78...`). Our measurement: the table the public 11.20 portfolio uses (identical across pramitdas, yoyobar,
  isabe11am00re and dmitriigluzdov v60/v61) shares 53% of the words with D35: batches 6 to 14 are 69% to 88% identical, batches
  0 to 5 only 1% to 16%. So the early batches were re-rounded ("reordered prefix", `compile_reordered_prefix.py`,
  `prefix_*.py`), which is where products went from 212 to 193 to 189 and Toffolis per pass from 4,151 to 4,074. [M for the
  fractions; the identity of that table with 91d0ad25 is [I], `best/dfthcsos` is not present in this worktree]
- Of the final gain over the public 11.20 (299.61 M to 296.64 M, 1.0%): angle Toffolis 8,302 to 8,148 and lambda_eff
  46.891 to 46.907 (slightly worse). So all of D35's improvement is the loaders. [M, `dfthcsos-cost-model.md` for 91d0ad25]

### Open items he leaves [V/I]

- Circuits k = 0 to 7 are 110 products above the bound (2,945 against 15 x 189 = 2,835 per pass); `climb147.py` and
  `add_k4_cuts.py` are the attempts to close that.
- `exact_affine_ccx_audit.py` looks for CCX gates replaceable by affine maps on the legal endpoints; audit only, no result in the zip.
- The 69 high ANDs are recomputed in every circuit (1,034 per pass, 25% of the loaders) and the endpoint trick is used only
  for the helper.
- The vectors and the Lambda are inherited, nothing in the zip improves the basin.

### Ranked ways to beat 11.31

Estimates are model scores at his `lambda_eff` unless stated. "Floor" means an assumption, not a construction.

| rank | lever | gain over 11.31 | needs | risk | tag |
|---:|---|---:|---|---|---|
| 0 | match: explicit-plan path (section 3, items 1 to 4) | 0% | ~150 lines, tests, one official verify | low | [I] |
| 1 | recode batches 0 to 7 to the 189-product level (move words under the five LSB and the parity codes, new plans) | +1.6% (11.51) | word moves with exact pricing and weight refit (his research code shows how), a cut search we do not have | medium to high | [M] bound |
| 2 | wider circuits at another split: lb = 5 gives H = 39, 53 ANDs per circuit, J = 8 fits 128 qubits (11 + 64 + 53), K = 10; products floor 209 | up to +18% (13.3) | a table with cut structure on 11 blocks and 56 coded planes, a cut search for it; Q grows 427 to 451 | high; the floor assumes cuts exist | [I] |
| 3 | weights-only refit with words frozen (circuits unchanged, `rebuild.py:6`) | under 0.1% | his `alfit.py` style | low value | [M] 91d0ad25's independent refit of the older words ends at Lambda 282.77 against 282.97 here |
| 4 | fewer bits (7 or 6) | model alone -3.2% / -6.3% cost; loader scaling would add up to about 8% more | a different basin | ruled out: our 7-bit table fails error_2 by 8.8x (`dfthcsos-low-brot.md`) and the shape's continuous floor is 0.0192 against 0.02 | [M] |
| 5 | smaller shape (R, B, C) for fewer T_prep Toffolis; e.g. (6, 132, 36) scores 12.5 at fixed loaders | up to +10% | a new fit at that shape that passes the gates | unknown; the continuous floor of (8, 143, 44) is already within 4% of the gate | [M] model, [I] feasibility |
| 6 | fewer qubits | not a lever | Q is 84 + 40 + 303, the 303 is the inner QROAM at k = 4, one qubit class below the cliff (k = 5 needs 606 against 600 allowed; brot 9 would be 0.61x) | | [M] |
| 7 | own basin: a continuous fit that reaches his Lambda | see below | | high | [I] |

Wider circuits are the only lever with double-digit headroom, and also the least certain. A lower-risk first experiment for it
is to run our matroid planner on his table at J = 5 with cuts taken from his plans, then ask what dimension a lb = 5, J = 6 layout
needs, before touching any fit.

### Starting from his table versus finding our own basin

His table already combines the three things we lack: a basin with Lambda 283, 8-bit rounding that passes both 0.02 gates,
and a table coded for the loader. Our E040 pipeline is at 11 bits with Lambda 489 and the per-plane loader. A rough chain
with the cost model [I]: Lambda 489 to 283 alone takes E040 from 2.50x to 2.50 x 63.14 / 46.91 = 3.4x; moving to 8 bits at
the same shape (model 5.3x at lambda_eff 63) gives 7.1x at his lambda_eff; a cut-planned loader instead of per-plane (angle
Toffolis 10,096 to 8,148) gives about 8.5x, still below 11.3 because our shapes (8, 176, 56) carry more Q and T_prep than his
(8, 143, 44). So the own-basin route does not catch his table unless the shape also shrinks, and it needs three results at
once. It is worth doing only as a test of whether the Lambda gap is basin or objective:

- Item 7a (cheap, CPU): run an `alfit`-style constrained refit (minimise lambda_eff subject to error gates, `w = p - n`) on OUR
  vectors (fit-b decoded at near-continuous precision). If Lambda drops from about 490 toward 300 and `w` grows exact zeros, the
  gap was the objective, and our earlier L1-at-the-end finding (7% of Lambda for 7% of error_2) came from the method. If not,
  it is the basin, and the GPU run with a Lambda penalty from the start is the next step.
- Item 7b: the vector locality of his table (participation ratio 4.4, dominant orbital) is a property of the optimum, not of
  a sparsity pattern (`dfthcsos-stage2.md`); structured starts did not reproduce it.

## Ideas to log in `docs/PROVENANCE.md` (own words; not edited here)

| idea | source | what we will rewrite |
|---|---|---|
| Free low lines from the old word registers: the helper bit (bit 7 XOR bit 6) is the same pure low monomial in every batch, so after one CX the old words already hold five degree-2 low monomials | syed3000 `dfthcsos_source_zip` (Apache-2.0), `compiler/emit_plan.py`, `helper_coordinates.py`, read 2026-11-15 | helper trick in `anf.py` and in `post.angles_of` (gauge choice theta or theta + pi per edge) |
| Output relations as code: LSB of each word and the parity of bit 1 over a batch get no nonlinear low part, so those planes cost nothing in the cut count; each relation removes about 4 products | same, `research/scripts/relations.py`, `parity_code.py`, plans' `method` strings | a relation counter over our own tables, then QAT moves that preserve it |
| Explicit product plan as data (l1, l2, out), coordinates h1 and h2 recomputed from the words | same, `compiler/emit_plan.py:41-51` | explicit-plan adapter for `matroid.build_pair_loader` |
| Pad the 12 unused address rows to keep the target inside the plan span | same, `compiler/padding_completion.py` | triangular solve for the free ANF coefficients |

## Reproduce

All numbers above come from small scripts (seconds each, `.venv/bin/python -I`, no torch): load `submission.npz` as data,
`dfthcsos.verify.evaluate_words` for the metrics, `dfthcsos_model.score` for costs, `dfthcsos_gen.bilinear.centered_rank`
and `dfthcsos_gen.anf.anf_toffolis` for our planner counts, and a 60-line GF(2) span test for the plans. The ledger was not
touched (no verifier run).
