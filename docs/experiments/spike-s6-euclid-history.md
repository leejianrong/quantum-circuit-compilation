# S6: in-place Euclid history for the reciprocal scan (QCC-64)

Hypothesis: an in-place Euclid history exists that makes the reciprocal-polynomial scan (`docs/experiments/dqi-psi.md`, 23 Toffolis
per position) buildable, worth about ratio 10 on the old design. Kill criterion: no scheme found in 3 days of classical analysis.

## Verdict: killed, and obsolete

1. **The premise is gone.** The "ratio about 10" was computed against the dialog-free BM decoder (ratio 7.76, scan 96 per position,
   386k of 741k Toffolis). Today's frontier circuits, ours (`fixed4`, 67.30x) and the public 70.04x, scan at **11 Toffolis per
   position** (4,095 x 11 = 45,045 T, 11.7% of 384,762; `docs/log/entries/2026-11-15-dqi-stage-ledgers.md`). The reciprocal scan
   costs 23 per position, about 94k, twice as much. Even a free in-place history would not make it competitive.
2. **The history problem was already a dead end** (`dqi-psi.md`, time-boxed session 2026-11-13): the swap bit is ambiguous after the
   step, the quotient is destroyed unless parked in `delta`-dependent slots (over 40k Toffolis of select and alignment), and the out
   of place version raises `Q` by 25% for a net loss of about 20%.
3. The remaining DQI gap is not the scan: 759 T of it is the adaptive gauge scan, and the main part is the unconditioned CSWAPs of
   the outer (`docs/experiments/dqi-70x-study.md`).

Lesson: re-check that a research idea's baseline still exists before spending on it. This one was costed against a design that
the frontier left behind.
