---
id: 2026-11-16-learning-track-figures-and-widgets
date: 2026-11-16
title: "Learning track made visual: 7 code-generated figures, 4 interactive widgets tested against the Python cost model, math, and a nav that reaches every page"
type: decision
benchmark: docs
methods: [docs-site, figures, widgets]
status: done
outcome: positive
prs: [190, 191, 198]
backfilled: false
licence_touched: false
---

## Question

The learning track was text and code. Can it teach with figures and interaction while staying static, offline,
deterministic and tested, and without a new build tool?

## Setup

Zensical 0.1.0, on `main` at the start of the work (`5e17635`). Options weighed and the choice: matplotlib to committed SVG
for static figures (plots extra, already in CI), vanilla JavaScript modules for widgets (no framework, no CDN),
MathJax vendored. Plotly or D3 from a CDN and Pyodide were rejected (network needed, size, dependency). Tested in
Chromium through Playwright on the dark and light themes; the Playwright and Chromium install is local only.

## Results

### Quantitative

| Item | Before | After |
|---|---|---|
| Pages linked from the nav | 14 of 67 | all of them, enforced by a test |
| Learning-track figures | 0 | 7 SVGs from `analysis/learn_figures.py`, drawn with an own circuit drawer |
| Interactive widgets | 0 | 4: phase and interference, cost with lines of equal score, MBUC stepper, dfthcsos score and gates |
| Formulas | none | MathJax 3.2.2 (SVG output, vendored, works offline) |
| Widget maths tested against Python | n/a | `lambda_eff`, the verifier gates, the score, interference, `Q*C` and `R*Q^2*T`, MBUC signs (Node against the real `dfthcsos_model` and numpy) |

### Qualitative

* The iso-cost figures and widgets plot real ledger rows; a test checks each point against `ledger/results.jsonl`.
  The dqi lines use `R(eps) = 1.2`; measured values on the plotted circuits are 1.19 to 1.22, so a point's printed ratio
  can differ from its verified ratio in the second digit (65.70 against 65.77 for our `fixed` circuit).
* Mermaid already worked: Zensical turns it on by default, but loads it from a CDN at view time (not offline).
* The widget `E_gap` slider shows the verifier's cliff: crossing 3.914898 changes the score by a hair and flips the
  circuit from accepted to rejected.
* The build only warns on a broken link and exits 0. A broken link in the generated corrections page went unnoticed
  until corrections existed. `zensical build --strict` aborts on warnings, so `make docs` now uses it.
* An earlier statement in this project's PR text, "9 of 70 pages in the nav", was wrong; the correct count was 14 of 67.

## Decision

Keep the widgets small, dependency-free and tested. Remaining from the plan: more figures for the primers (qubits and
gates, kickmix hands-on, the benchmark pipelines) and a Playwright run in CI if browser tests become worth the install time.

## Reproduce

```
make learn-figures        # redraws docs/img/learn/*.svg and the widget data module
uv run pytest tests/unit/test_learn_figures.py tests/unit/test_widgets_parity.py
uv sync --inexact --extra shots && uv run playwright install chromium
uv run pytest tests/unit/test_widgets_browser.py
make docs
```

## Links

PRs 190 (math, nav, CI), 191 (figures and drawer), 198 (widgets); `analysis/learn_figures.py`,
`docs/javascripts/widgets*.mjs`, `analysis/numbers/learn.json`.
