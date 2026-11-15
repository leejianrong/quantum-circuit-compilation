// Pure maths behind the learning-track widgets. No DOM, so Node can test it against the Python cost model
// (tests/unit/test_widgets_parity.py). Keep every formula identical to its Python twin:
//   lambdaEff, gates       <-> src/dfthcsos_model/model.py (lambda_eff, passes_gates)
//   interference           <-> numpy: H @ diag(1, e^(i*theta)) @ H @ |0>
//   benchCost, ratio       <-> docs/learn/costs-and-mbuc.md (invsqrt Q*C; dqi R*Q^2*T)
//   mbucStep               <-> docs/learn/costs-and-mbuc.md (bit-plus-phase bookkeeping)

export const GATE_LIMITS = { err: 0.02, lamFloor: 49.0, eGapFloor: 3.914898 };

export function lambdaEff(lam, eGap) {
  return Math.sqrt(eGap * (2 * lam - eGap));
}

// The verifier's accuracy gates. `pass` is true only if every one holds (floors are strict).
export function gates({ lam, eGap, err1, err2 }) {
  const g = {
    err1: err1 <= GATE_LIMITS.err,
    err2: err2 <= GATE_LIMITS.err,
    lam: lam > GATE_LIMITS.lamFloor,
    eGap: eGap > GATE_LIMITS.eGapFloor,
    band: eGap > 0 && eGap < 2 * lam,
  };
  g.pass = g.err1 && g.err2 && g.lam && g.eGap && g.band;
  return g;
}

export function dfthcsosScore(p, baseline) {
  const le = p.band === false ? NaN : lambdaEff(p.lam, p.eGap);
  const score = le * p.t * p.q;
  return { lambdaEff: le, score, ratio: baseline / score, gates: gates(p) };
}

// H P(theta) H |0>: amplitudes as [re, im] pairs and the two outcome probabilities.
export function interference(theta) {
  const c = Math.cos(theta);
  const s = Math.sin(theta);
  const a0 = [(1 + c) / 2, s / 2];
  const a1 = [(1 - c) / 2, -s / 2];
  const p = (a) => a[0] * a[0] + a[1] * a[1];
  return { a0, a1, p0: p(a0), p1: p(a1) };
}

// Cost of a circuit with Q qubits and y = C (invsqrt, cost = Q*C) or y = T (dqi, cost = R*Q^2*T).
export function benchCost(bench, q, y, rEps = 1.2) {
  return bench === "invsqrt" ? q * y : rEps * q * q * y;
}

export function ratio(bench, cost, baselines) {
  return baselines[bench] / cost;
}

// Fractional change of y that keeps the cost fixed after the qubits change by dq (0.1 = 10% more qubits).
export function equivalentChange(bench, dq) {
  const k = bench === "invsqrt" ? 1 : 2;
  return (1 + dq) ** -k - 1;
}

// Measurement-based uncomputation of an AND: one Toffoli computes it, HMR measures the ancilla into m,
// and a CZ on (a, b) runs when m is 1. Signs are +1 or -1. `repair: false` skips the CZ.
export function mbucStep(a, b, m, repair = true) {
  const f = a & b;
  const afterHmr = m & f ? -1 : 1;
  const applied = repair && m === 1;
  const final = applied && f ? -afterHmr : afterHmr;
  return { f, afterHmr, applied, final, toffolis: 1 };
}
