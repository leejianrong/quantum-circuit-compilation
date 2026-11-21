# S3: invsqrt table and loader co-design as exact optimisation (QCC-61)

Written before any code (2026-11-20). Source for the facts is `docs/experiments/invsqrt-syed-decode.md` section 4, idea 2, and the
reference build we reproduce (`docs/log/entries/2026-11-20-invsqrt-port-finish.md`).

## Hypothesis

The 46-qubit line builds a 128-row, 16-output table (13 coefficient bits and 3 metadata bits) and loads it twice (first loader 56 ANDs,
second 70 ANDs), plus 118 Toffolis of coefficient rows. That is 244 of 1,511.57 Toffolis (16%). The table was fitted once to maximise the
accuracy margin; only the slope bit is implicit. The worst error is 0.9736 of the tolerance, so 2.7% of the tolerance is unused. Our claim:
some table bits can be moved inside that slack so that the exact minimum-AND loader for the moved table is smaller by at least 1% of the
circuit cost (about 15 Toffolis, 800 modelled cost).

## Where it can and cannot pay

* The port reproduces the 46-qubit line (80,162.76, 25.91x). The 44-qubit circuits of v13 (27.77x in `best/`) have no source we hold, so a
  gain here is measured on the 46-qubit line, not on the 44-qubit frontier as the card says. A 1% gain there gives about 26.2x, below
  `best/`. The result only helps the score if (a) the technique transfers to a 44-qubit build that we write ourselves, or (b) it
  combines with width reductions (Q45 and below, idea 1 of the decode study). The card's "done when" is therefore read as: gain over
  1% on the 46-qubit port with the exact proof passing, or killed.
* The slack is shared with the 33 rotation sites (about 7 Toffoli equivalents each) and with the arithmetic rounding. Spending it on the
  table means fewer rotations can be saved elsewhere; stage 1 measures that trade.

## Method, in stages, each with a kill rule

1. **Freedom of the table (read-only, no circuit).** From the pinned table model and the full-domain integer oracle (3,133,452 inputs),
   compute for each of the 128 x 13 coefficient bits whether flipping it alone keeps worst error/tolerance below 1, and the error
   increase it costs. *Kill the spike if* fewer than 16 single flips are feasible (the loaders then have no useful don't-care
   freedom) [predicted: dozens, since 2.7% of tolerance is large next to a unit of the last coefficient bit; this is the number that could
   falsify the hypothesis].
2. **One segment, exact.** Take one output plane group of the first loader (the part with the most ANDs). Find the exact minimum-AND
   program for the current table (SAT or exhaustive search with replay on 128 rows) and for the table with the stage-1 freedom as
   don't-cares (ILP over the feasible flip set, then SAT). *Kill if* the best saving over the segment, scaled to all 16 planes and both
   loaders, is under 8 ANDs (0.5%).
3. **Joint table and loader.** Choose the flip set that jointly minimises both loaders and the coefficient rows under the margin
   (ILP: flips x error contribution <= slack). *Kill if* the joint saving is under 15 Toffolis.
4. **Build and verify.** Patch the table in the working port (new patch module, ours), rebuild in the sandbox, run the finishing passes
   (the passes must still find their savings), exact proof, official verifier at 10 salts through the container or Kaggle.

## Measurements recorded for every stage

Number of feasible flips; error/tolerance before and after; ANDs per loader before and after; modelled cost and Toffolis before and
after; the exact proof status. All on the sandboxed port; the table and oracle come from the downloaded archive and stay untouched.

## Tooling needed

A table extractor and error oracle (own code, read-only on the archive, runs in the sandbox because the oracle needs `kickmix.so`),
an ILP (HiGHS, already used in `docs/experiments/invsqrt-onepass.md`) and a small exact AND-program search (our own).

## Update 2026-11-21: the frontier moved to 43 qubits with 0.3% slack

syed3000's v17 circuit (`70fe5f79`, now in `best/`) reports a worst error over tolerance of 0.9969, so about 0.3% of the tolerance is
unused against 2.7% on the 46-qubit line this plan was written for ([reading](../log/entries/2026-11-21-invsqrt-v17-generator-reading.md)).
Stage 1 would almost certainly fail there (almost no single-bit table flip fits). S3 stays valid only on the 46-qubit port, which is
below `best/`, so it is parked rather than started; QCC-61 moves to the owner's backlog unless the v17 generator is ported and
the slack proves larger in its table stage.
