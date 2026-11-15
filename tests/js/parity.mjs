// Node side of tests/unit/test_widgets_parity.py: evaluates the widget core on the golden inputs the
// Python test generated and prints the results as JSON.
import { readFileSync } from "node:fs";
import {
  benchCost,
  dfthcsosScore,
  equivalentChange,
  gates,
  interference,
  lambdaEff,
  mbucStep,
} from "../../docs/javascripts/widgets-core.mjs";

const g = JSON.parse(readFileSync(process.argv[2], "utf8"));
const out = {
  lambdaEff: g.lambdaEff.map(([lam, eGap]) => lambdaEff(lam, eGap)),
  gates: g.gates.map((p) => gates(p).pass),
  score: g.score.map((p) => dfthcsosScore(p, g.baseline).score),
  interference: g.interference.map((t) => {
    const r = interference(t);
    return [r.a0, r.a1, r.p0, r.p1];
  }),
  benchCost: g.benchCost.map(([b, q, y]) => benchCost(b, q, y, g.rEps)),
  equivalent: g.equivalent.map(([b, dq]) => equivalentChange(b, dq)),
  mbuc: g.mbuc.map(([a, b, m, repair]) => {
    const r = mbucStep(a, b, m, repair);
    return [r.afterHmr, r.final];
  }),
};
console.log(JSON.stringify(out));
