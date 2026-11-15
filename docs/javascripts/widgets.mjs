// Interactive widgets for the learning track. A page places <div class="qcc-widget" data-widget="NAME"></div>
// and this module mounts NAME into it. The maths is in widgets-core.mjs (tested against Python); the numbers
// come from widgets-data.mjs (generated). No dependencies, no network.
import {
  GATE_LIMITS,
  benchCost,
  dfthcsosScore,
  equivalentChange,
  interference,
  lambdaEff,
  mbucStep,
  ratio,
} from "./widgets-core.mjs";
import { DATA } from "./widgets-data.mjs";

const SVGNS = "http://www.w3.org/2000/svg";

function el(tag, attrs = {}, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v);
  }
  for (const kid of kids) e.append(kid);
  return e;
}

function sv(tag, attrs = {}, text) {
  const e = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (text !== undefined) e.textContent = text;
  return e;
}

const fmt = (x, d = 3) => (Number.isFinite(x) ? x.toLocaleString("en-US", { maximumSignificantDigits: d + 2 }) : "n/a");

// A labelled slider. `log` maps a 0..1000 position to a log-spaced value.
function slider({ label, min, max, step, value, log = false, unit = "", onChange }) {
  const out = el("output", { class: "qcc-out" });
  const toValue = (pos) => (log ? min * (max / min) ** (pos / 1000) : pos);
  const toPos = (v) => (log ? (1000 * Math.log(v / min)) / Math.log(max / min) : v);
  const input = el("input", {
    type: "range",
    min: log ? 0 : min,
    max: log ? 1000 : max,
    step: log ? 1 : step,
    value: toPos(value),
  });
  // `current` keeps the exact value (a preset is not rounded to the slider's grid until the user moves it).
  let current = value;
  const show = () => {
    out.textContent = `${fmt(current, 5)}${unit}`;
  };
  input.addEventListener("input", () => {
    current = toValue(Number(input.value));
    show();
    onChange(current);
  });
  show();
  return {
    node: el("label", { class: "qcc-row" }, el("span", { class: "qcc-lab" }, label), input, out),
    set(v) {
      current = v;
      input.value = toPos(v);
      show();
    },
    get: () => current,
  };
}

function chip(text, ok) {
  return el("span", { class: `qcc-chip ${ok ? "ok" : "bad"}` }, `${ok ? "✓" : "✗"} ${text}`);
}

// --- 1. phase and interference ------------------------------------------------------------------

function mountInterference(root) {
  let theta = Math.PI;
  const view = el("div", { class: "qcc-view" });
  const note = el("p", { class: "qcc-note" });
  const draw = () => {
    const r = interference(theta);
    const W = 360;
    const H = 170;
    const svg = sv("svg", { viewBox: `0 0 ${W} ${H}`, class: "qcc-svg", role: "img", "aria-label": "interference" });
    // unit circle with the phase point
    const cx = 85;
    const cy = 85;
    const R = 60;
    svg.append(sv("circle", { cx, cy, r: R, class: "qcc-line", fill: "none" }));
    svg.append(sv("line", { x1: cx - R - 8, y1: cy, x2: cx + R + 8, y2: cy, class: "qcc-line" }));
    svg.append(sv("line", { x1: cx, y1: cy - R - 8, x2: cx, y2: cy + R + 8, class: "qcc-line" }));
    const px = cx + R * Math.cos(theta);
    const py = cy - R * Math.sin(theta);
    svg.append(sv("line", { x1: cx, y1: cy, x2: px, y2: py, class: "qcc-a", "stroke-width": 2 }));
    svg.append(sv("circle", { cx: px, cy: py, r: 5, class: "qcc-a-fill" }));
    svg.append(sv("text", { x: cx, y: 12, "text-anchor": "middle", class: "qcc-t" }, "phase e^(iθ)"));
    // probability bars
    const bx = 200;
    for (const [i, p] of [r.p0, r.p1].entries()) {
      const h = 100 * p;
      svg.append(sv("rect", { x: bx + i * 70, y: 140 - h, width: 40, height: Math.max(h, 0.5), class: i ? "qcc-b-fill" : "qcc-a-fill" }));
      svg.append(sv("text", { x: bx + i * 70 + 20, y: 156, "text-anchor": "middle", class: "qcc-t" }, i ? "|1>" : "|0>"));
      svg.append(sv("text", { x: bx + i * 70 + 20, y: 134 - h, "text-anchor": "middle", class: "qcc-t" }, p.toFixed(3)));
    }
    svg.append(sv("text", { x: bx + 55, y: 12, "text-anchor": "middle", class: "qcc-t" }, "probability after H, phase, H"));
    view.replaceChildren(svg);
    const deg = Math.round((theta * 180) / Math.PI);
    note.textContent =
      `Phase ${deg}°: P(|0>) = cos²(θ/2) = ${r.p0.toFixed(3)}. ` +
      (deg % 360 === 180 ? "That is Z: the phase turns |0> into |1>." : deg % 360 === 0 ? "No phase: H H is the identity." : "");
  };
  const s = slider({
    label: "phase θ",
    min: 0,
    max: 360,
    step: 1,
    value: 180,
    unit: "°",
    onChange: (v) => {
      theta = (v * Math.PI) / 180;
      draw();
    },
  });
  const presets = el(
    "div",
    { class: "qcc-presets" },
    ...[["none", 0], ["T (45°)", 45], ["S (90°)", 90], ["Z (180°)", 180]].map(([name, deg]) =>
      el("button", { type: "button", onclick: () => { s.set(deg); theta = (deg * Math.PI) / 180; draw(); } }, name),
    ),
  );
  root.replaceChildren(s.node, presets, view, note);
  draw();
}

// --- 2. cost: qubits against Toffolis with lines of equal score ---------------------------------

function mountIsoCost(root) {
  const st = { bench: "dqi" };
  const body = el("div", { class: "qcc-body" });
  const pick = el(
    "div",
    { class: "qcc-presets" },
    ...["invsqrt", "dqi"].map((b) =>
      el("button", { type: "button", "data-b": b, onclick: () => { st.bench = b; build(); } }, `${b}: ${b === "invsqrt" ? "Q · C" : "R · Q² · T"}`),
    ),
  );
  function build() {
    const ax = DATA.axes[st.bench];
    const pts = DATA[st.bench].points.map((p) => ({
      label: p.label,
      kind: p.kind,
      q: p.qubits,
      y: st.bench === "invsqrt" ? p.cost / p.qubits : p.toffoli,
      off: p.offset || [7, -5],
    }));
    const start = st.bench === "invsqrt" ? { q: 93, y: 1809 } : { q: 890, y: 391326 };
    let q = start.q;
    let y = start.y;
    const readout = el("p", { class: "qcc-readout" });
    const trade = el("p", { class: "qcc-note" });
    const plot = el("div", { class: "qcc-view" });
    const W = 420;
    const H = 260;
    const m = { l: 56, r: 40, t: 12, b: 36 };
    const X = (v) => m.l + ((Math.log(v) - Math.log(ax.q[0])) / (Math.log(ax.q[1]) - Math.log(ax.q[0]))) * (W - m.l - m.r);
    const Y = (v) => H - m.b - ((Math.log(v) - Math.log(ax.y[0])) / (Math.log(ax.y[1]) - Math.log(ax.y[0]))) * (H - m.t - m.b);
    const redraw = () => {
      const svg = sv("svg", { viewBox: `0 0 ${W} ${H}`, class: "qcc-svg", role: "img", "aria-label": "cost plot" });
      svg.append(sv("rect", { x: m.l, y: m.t, width: W - m.l - m.r, height: H - m.t - m.b, fill: "none", class: "qcc-line" }));
      const base = DATA.baselines[st.bench];
      const rEps = DATA.dqi_r_eps;
      for (const lv of ax.levels) {
        const target = base / lv;
        const xs = Array.from({ length: 60 }, (_, i) => Math.exp(Math.log(ax.q[0]) + ((Math.log(ax.q[1]) - Math.log(ax.q[0])) * i) / 59));
        const path = xs
          .map((qq) => [qq, target / benchCost(st.bench, qq, 1, rEps)])
          .filter(([, yy]) => yy >= ax.y[0] && yy <= ax.y[1])
          .map(([qq, yy], i) => `${i ? "L" : "M"}${X(qq).toFixed(1)},${Y(yy).toFixed(1)}`)
          .join("");
        if (path) svg.append(sv("path", { d: path, class: "qcc-iso", fill: "none" }));
        const lastIn = xs.map((qq) => [qq, target / benchCost(st.bench, qq, 1, rEps)]).filter(([, yy]) => yy >= ax.y[0] * 1.05 && yy <= ax.y[1] * 0.95).pop();
        if (lastIn) svg.append(sv("text", { x: X(lastIn[0]) + 3, y: Y(lastIn[1]) - 3, class: "qcc-t small" }, `${lv}x`));
      }
      for (const p of pts) {
        svg.append(sv("circle", { cx: X(p.q), cy: Y(p.y), r: 4.5, class: p.kind === "ours" ? "qcc-a-fill" : p.kind === "public" ? "qcc-b-fill" : "qcc-r-fill" }));
        svg.append(sv("text", { x: X(p.q) + p.off[0], y: Y(p.y) + p.off[1], "text-anchor": p.off[0] < 0 ? "end" : "start", class: "qcc-t small" }, p.label));
      }
      svg.append(sv("path", { d: `M${X(q) - 7},${Y(y)}h14M${X(q)},${Y(y) - 7}v14`, class: "qcc-you", fill: "none", "stroke-width": 2.5 }));
      svg.append(sv("text", { x: (m.l + W - m.r) / 2, y: H - 6, "text-anchor": "middle", class: "qcc-t" }, "logical qubits Q"));
      svg.append(sv("text", { x: 12, y: H / 2, "text-anchor": "middle", class: "qcc-t", transform: `rotate(-90 12 ${H / 2})` }, ax.ylabel));
      plot.replaceChildren(svg);
      const cost = benchCost(st.bench, q, y, rEps);
      readout.textContent = `Your circuit (the cross): cost ${fmt(cost, 4)}, ratio ${ratio(st.bench, cost, DATA.baselines).toFixed(2)}x against the reference${st.bench === "dqi" ? " (R(ε) taken as 1.2)" : ""}.`;
      const unitName = st.bench === "invsqrt" ? "C" : "T";
      trade.textContent = `Cutting the qubits by 10% pays for ${(equivalentChange(st.bench, -0.1) * 100).toFixed(1)}% more ${unitName} at the same cost; a 10% cut in ${unitName} is only a 10% cut in cost.`;
    };
    const sq = slider({ label: "qubits Q", min: ax.q[0], max: ax.q[1], value: q, log: true, onChange: (v) => { q = v; redraw(); } });
    const sy = slider({ label: ax.ylabel, min: ax.y[0], max: ax.y[1], value: y, log: true, onChange: (v) => { y = v; redraw(); } });
    body.replaceChildren(sq.node, sy.node, plot, readout, trade);
    redraw();
  }
  root.replaceChildren(pick, body);
  build();
}

// --- 3. MBUC: one Toffoli, measure, repair -----------------------------------------------------

function mountMbuc(root) {
  const st = { a: 1, b: 1, m: 1, repair: true };
  const steps = el("ol", { class: "qcc-steps" });
  const table = el("div", { class: "qcc-view" });
  const mk = (name, label, opts) =>
    el("label", { class: "qcc-check" }, el("input", { type: "checkbox", ...opts, onchange: (e) => { st[name] = e.target.checked ? 1 : 0; if (name === "repair") st.repair = !!e.target.checked; redraw(); } }), label);
  const sgn = (s) => (s > 0 ? "+1" : "-1");
  function redraw() {
    const r = mbucStep(st.a, st.b, st.m, st.repair);
    steps.replaceChildren(
      el("li", {}, `Toffoli: the ancilla becomes a AND b = ${r.f}. Cost: 1 Toffoli.`),
      el("li", {}, `HMR: measure the ancilla, outcome m = ${st.m}. The state now carries the sign (-1)^(m·a·b) = ${sgn(r.afterHmr)}.`),
      el("li", {}, st.repair ? (st.m ? `m is 1, so apply CZ on a and b: it flips the sign when a·b = 1 (here ${r.f ? "yes" : "no"}).` : "m is 0, so there is nothing to repair.") : "Repair skipped."),
      el("li", { class: r.final === 1 ? "good" : "bad" }, `Final sign ${sgn(r.final)}: ${r.final === 1 ? "clean, as if we had uncomputed with a second Toffoli." : "wrong: the leftover sign would spoil later interference."}`),
    );
    const rows = [];
    for (const a of [0, 1]) for (const b of [0, 1]) for (const m of [0, 1]) {
      const w = mbucStep(a, b, m, false).final;
      const f = mbucStep(a, b, m, true).final;
      rows.push(el("tr", {}, ...[a, b, m, sgn(w), sgn(f)].map((x, i) => el("td", { class: i === 3 && w < 0 ? "bad" : i === 4 ? "good" : "" }, String(x)))));
    }
    table.replaceChildren(el("table", { class: "qcc-table" }, el("thead", {}, el("tr", {}, ...["a", "b", "m", "sign, no repair", "sign, with CZ"].map((h) => el("th", {}, h)))), el("tbody", {}, ...rows)));
  }
  const m = el("label", { class: "qcc-check" }, "outcome m: ", el("select", { onchange: (e) => { st.m = Number(e.target.value); redraw(); } }, el("option", { value: 0 }, "0"), el("option", { value: 1, selected: "" }, "1")));
  root.replaceChildren(el("div", { class: "qcc-presets" }, mk("a", "a = 1", { checked: "" }), mk("b", "b = 1", { checked: "" }), m, mk("repair", "apply the CZ repair", { checked: "" })), steps, table);
  redraw();
}

// --- 4. dfthcsos: score and gates ----------------------------------------------------------------

function mountDfthcsos(root) {
  const p = { ...DATA.dfthcsos_presets[1] };
  const out = el("div", { class: "qcc-readout" });
  const chips = el("div", { class: "qcc-presets" });
  const sl = {};
  const redraw = () => {
    const r = dfthcsosScore(p, DATA.baselines.dfthcsos);
    const g = r.gates;
    chips.replaceChildren(
      chip(`error_1 ≤ ${GATE_LIMITS.err}`, g.err1),
      chip(`error_2 ≤ ${GATE_LIMITS.err}`, g.err2),
      chip(`Lambda > ${GATE_LIMITS.lamFloor}`, g.lam),
      chip(`E_gap > ${GATE_LIMITS.eGapFloor}`, g.eGap),
      chip("0 < E_gap < 2 Lambda", g.band),
    );
    out.replaceChildren(
      el("p", {}, `lambda_eff = √(E_gap (2Λ − E_gap)) = ${fmt(r.lambdaEff, 5)}`),
      el("p", {}, `score = lambda_eff · T_total · Q_total = ${fmt(r.score, 5)}  (ratio ${Number.isFinite(r.ratio) ? r.ratio.toFixed(2) : "n/a"}x)`),
      el("p", { class: g.pass ? "good" : "bad" }, g.pass ? "Accepted: every gate holds." : "Rejected by the verifier, whatever the score: a failed gate rejects the circuit."),
    );
  };
  const mkS = (key, cfg) => {
    sl[key] = slider({ ...cfg, value: p[key], onChange: (v) => { p[key] = v; redraw(); } });
    return sl[key].node;
  };
  const presets = el("div", { class: "qcc-presets" }, ...DATA.dfthcsos_presets.map((q) => el("button", { type: "button", title: q.note, onclick: () => { Object.assign(p, q); for (const k of Object.keys(sl)) sl[k].set(p[k]); redraw(); } }, q.name)));
  root.replaceChildren(
    presets,
    mkS("lam", { label: "Lambda", min: 40, max: 600, log: true }),
    mkS("eGap", { label: "E_gap", min: 3.8, max: 4.2, step: 0.0005 }),
    mkS("t", { label: "T_total", min: 5000, max: 120000, log: true }),
    mkS("q", { label: "Q_total", min: 100, max: 1000, log: true }),
    mkS("err1", { label: "error_1", min: 0, max: 0.04, step: 0.0001 }),
    mkS("err2", { label: "error_2", min: 0, max: 0.04, step: 0.0001 }),
    chips,
    out,
  );
  redraw();
}

const REGISTRY = {
  interference: mountInterference,
  "iso-cost": mountIsoCost,
  mbuc: mountMbuc,
  dfthcsos: mountDfthcsos,
};

function mountAll() {
  for (const root of document.querySelectorAll(".qcc-widget")) {
    const mount = REGISTRY[root.dataset.widget];
    if (mount && !root.dataset.mounted) {
      root.dataset.mounted = "1";
      mount(root);
    }
  }
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mountAll);
else mountAll();

export { lambdaEff };
