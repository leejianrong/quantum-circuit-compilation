# Dashboard gap analysis: what indah has, what we need

Input to QCC-44, QCC-46 and QCC-47 (see [MEASUREMENT.md](MEASUREMENT.md) and
[ADR-0008](adr/0008-measurement-ledger-v2-and-dashboard.md)). The owner's position is that we do
not bend the dashboard to fit whatever indah offers: where a better visual needs a new or richer
indah component, indah itself gets improved. This page lists those components, sized, with a
fallback for each so the dashboard is never blocked.

Checked against the indah repo at commit `0ff8a14` (read only; nothing there was changed).
Paths are in that repo. `components.py` means `src/indah/components.py`, and `Chart.svelte` means
`frontend/src/Chart.svelte`. Line numbers were read on 2026-11-12. Indah's `AGENTS.md` says to trust
the code over its docs, so every row below comes from the code, not the website pages.

## What indah already does well

This is a long list, and it is why the gap list is short.

- **Reactive recompute.** A `Chart` (`components.py:1620`) takes `data` as a `Signal`, `Computed`
  or callable and redraws in the browser with uPlot, so a slider-driven cost model needs no
  special support. `rules` draws up to 12 labelled horizontal reference lines (`:1578`),
  `playhead` is a reactive vertical line, `shade_after` dims everything beyond it, `highlight`
  picks out one bar, `x_range`/`y_range` fix the axes. Series kinds are `line`, `scatter`, `bars`
  with `dash`, `alpha`, `width`, `size` (`:1538`, `Chart.svelte:42-60`). Colours accept
  `var(--token)`, so light and dark follow the Studio theme.
- **Heatmap** (`:1893`): column-major `z`, `row_labels`, `col_groups`, `null_color`,
  `origin="top"`, reactive `mark_x`/`mark_y` crosshair, custom colormaps. This is already the
  right component for a salt-by-benchmark pass/fail matrix.
- **Graph** (`:2313`): columnar wire form, per-node `label`, `group` (palette plus legend),
  `size`, `color`, explicit `x`/`y` with `layout="given"`; `selected`, `hovered` and `focus`
  signals; `highlight` of nodes and edges. Lazy-loaded (`graph.js`, 16 KB). Node click into a
  detail panel is a `Signal` plus `Show`/`Card`, no new work.
- **Table v2** (`:2719`): typed `Col` kinds (`text`, `mono`, `badge` with tones, `time`, `number`,
  `cell`), sort, search, paging, `selected`, `RowAction`, narrow-screen cards, `Stream` feeding.
- **Stat** (`:3126`), **Tabs** (`:4462`), **Grid/Row/Cell/SplitPane/MasterDetail**, **Pie**
  (`:1847`), **Progress** (`:3259`), **Badge**, **Steps** (`:785`), **BarStrip** (`:3292`),
  **Plot** (`:1486`, a Matplotlib `Figure` straight to a PNG data URI), **Image**
  (`:1289`, URL, bytes or `data:` URI, allowed by the CSP `img-src 'self' data:`), and
  `register_component(module=...)` (`custom.py:123`) for our own ES module when nothing fits.
- **Conventions.** Studio design system tokens, a Studio page per public name enforced by
  `tests/unit/test_studio_coverage.py`, strict CSP in the whole e2e suite, and a bundle budget
  (`docs/size-budget.json`) with a separate lazy budget per heavy module. Any new component should
  follow all four.

## (a) Matrix: needed element x tab x status

Status: **available** (works today), **partial** (works with a workaround or only some of the
element), **missing** (no way except a static image or our own JS module). "Gap" ids point to
section (b).

### Scoreboard

| Element | Status | indah component checked | Note | Gap |
|---|---|---|---|---|
| Score and ratio cards | available | `Stat` `components.py:3126` | big value, label, delta, help | |
| Delta colour that follows "lower is better" | partial | `Stat` `:3126` | colour is green unless the delta text starts with `-`; fine for ratios, wrong for Toffoli counts | G12 |
| Sparkline in a card | missing | `Stat` `:3126` | no spark prop | G11, G12 |
| Staircase (step) ratio-over-time line | partial | `Chart` `:1620`, `_SERIES_KINDS` `:1523` | only linear interpolation; the workaround is two points per change `(t, old), (t, new)` | G1 |
| Public frontier as a reference line | available | `_rules` `:1578` | horizontal, labelled, dashed, themed colour | |
| Vertical event annotations ("promoted v3") | missing | `playhead` `:1620` is one reactive x only | | G3 |
| Time x axis (dates) | missing | `Chart.svelte:161` sets `time: false` | x is a number; epoch seconds show as numbers | G4 |
| Log y axis | missing | `Chart.svelte:162-163` only a linear `range` | | G2 |
| Different x per series (ratio per benchmark, three series on different dates) | partial | `_to_rows` `:1607`, rows are `[x, y0, y1, ...]` | one shared x column; union the x values and put `None` in the gaps (JSON null, uPlot draws a gap) | G8 |
| Hover value readout | partial | legend values only (`Chart.svelte:178-184`) | no tooltip box, no click event back to Python | G5 |

### Cost explorer

| Element | Status | indah component checked | Note | Gap |
|---|---|---|---|---|
| Slider drives a recomputed chart | available | `Slider` `:327`, `Chart(data=Computed)` | | |
| Slider shows its current value | missing | `Node.svelte:681-697` | only the label; no readout | G13 |
| Slider that fires on release | missing | `Node.svelte:692` posts `input` on every move | each drag step spends a token of the shared `/api/event` bucket | G13 |
| Log-scaled slider (factorization size) | missing | `Slider` `:327` has `min/max/step` only | | G13 |
| Threshold or cliff marker (gate line, `Lambda` limit) | available | `rules` `:1578`, `playhead` | horizontal rule and vertical playhead, both reactive | |
| Shaded safe or failing region | partial | `shade_after` `:1620` | one-sided, tied to the playhead; no band | G3 |
| Gate pass/fail readouts | available | `Badge` `:595`, `Table` `Col(kind="badge", tones=...)` | `Stat` is not needed here | |
| Product of three terms on a log scale | missing | see log axis above | workaround: plot log10 and say so in the axis label | G2 |

### Anatomy

| Element | Status | indah component checked | Note | Gap |
|---|---|---|---|---|
| Flame or icicle chart of nested `mark` blocks | missing | none; `ImageOverlay` `:1430` is boxes on a raster | static fallback below | G9 |
| Show kickmix's own flame SVG | partial | `Image` `:1289` | an SVG `data:` URI in an `<img>` is displayed, but it is inert (no hover, no zoom, no click). Not run locally; verify before relying on it | G9 |
| Stage-share breakdown for one circuit | available | `Pie` `:1847`, `Table` | a table with a `Progress` per row (`:3259`) reads better than a pie | |
| Stacked bars per circuit | partial | `Chart` kind `bars` `Chart.svelte:46-53` | bars are drawn side by side, not stacked; `BarStrip` `:3292` stacks with tones but has no axis, no per-bar x labels beyond tooltips, and 8 to 240 px height | G6 |
| Category x axis (circuit names) | missing | `Chart.svelte:161` numeric x | `BarStrip.labels` is tooltip-only | G4 |
| Node click shows detail of a stage | missing | no `Chart` event; `Graph` has `selected` | | G5, G9 |

### Verifier theatre

| Element | Status | indah component checked | Note | Gap |
|---|---|---|---|---|
| Salt by benchmark pass/fail matrix | available | `Heatmap` `:1893` | `row_labels`, `col_groups`, `null_color`, `origin="top"` | |
| Per-salt tick strip (pass or fail per salt) | partial | `BarStrip` `:3292` | works as stacked `[1, 0]` (ok) or `[0, 1]` (err) bars with `tones=["ok","err"]`, `names`, `labels` for the salt id, up to 1440 bars; not usable inside a table cell; no gap between ticks control | G11 |
| Per-salt tick strip in a table row | missing | `Col(kind="cell")` `:2508`; `ALLOWED_TAGS` `protocol.py:115` has no `svg` or `canvas` | `Steps` is the only component bound in cells (`:785`, max 100 items, five fixed states) and it draws rings, not ticks | G11 |
| Cost spread across salts, strip plot | partial | `Chart` kind `scatter` | needs a numeric x (benchmark index plus a jitter we compute) and no category labels | G4, G7 |
| Box or violin of the spread | missing | none | | G7 |
| Margin versus accuracy gate | available | `rules` `:1578` on a scatter | | |
| "One failure rejects everything" emphasis | available | `Badge`, `Text(tone="err")`, `Stat` | | |

### Lineage

| Element | Status | indah component checked | Note | Gap |
|---|---|---|---|---|
| DAG from baseline to our circuits | available | `Graph` `:2313`, `layout="given"` | we compute layer x/y in Python, or use `layout="auto"`, which is a force layout and gives no left-to-right reading | G10 |
| Edge direction (arrowheads) | missing | `_GRAPH_EDGE_KEYS` `:2184` is `source target id label color`; nothing in `Graph.svelte` draws arrows | a lineage graph without direction is ambiguous | G10 |
| Dashed node (no-licence ancestor) | missing | `_GRAPH_NODE_KEYS` `:2183` has `color`, `group`, `size`, no stroke or dash | workaround: a `group` named "no licence" with its own colour and legend entry, plus a text label suffix. Colour is the only cue, which fails the colour-blind rule indah itself keeps for `Steps` and `BarStrip` | G10 |
| Coloured nodes by kind (ours, public, baseline) | available | `group`, `color`, legend | | |
| Node click opens a detail panel | available | `Graph(selected=Signal)` `:2313` plus `Show`/`Card`/`MasterDetail` | | |
| Highlight a path | available | `Graph(highlight=...)` | | |
| Edge labels | available | edge dict `label` | | |

### Experiments

| Element | Status | indah component checked | Note | Gap |
|---|---|---|---|---|
| Table of attempts and outcomes | available | `Table` `:2719`, `Col(kind="badge", tones=...)`, `kind="time"`, sort, search, paging | | |
| Row click to a detail drawer | available | `Table(selected=)`, `Drawer`, `RowAction` | | |
| Sparkline per row (cost over parent chain) | missing | `Col(kind="cell")` render spec, no svg/canvas | | G11 |
| Funnel (screened, verified, promoted, submitted) | partial | `Progress` `:3259` per stage in a `Column`, or `Table` | drawn as separate labelled bars, no shared scale guarantee unless `max` is set to the first stage | G6 |
| Timeline of experiments | partial | `Steps` `:785` (max 100, no time axis); `Table` `kind="time"` | no time-positioned lanes | G9 |
| Live append as experiments finish | available | `Stream`-fed `Table`, `Chart.push` | | |

### The six plots, as dashboard visuals

These stay matplotlib PNGs for the README and docs site (MEASUREMENT.md). The question here is
what an interactive dashboard version needs. The `Plot` component renders the same `Figure`, so the
fallback is always one line.

| Plot | Visual elements needed | Best indah path today | Gaps |
|---|---|---|---|
| 1. Score over time, staircase, public frontier | step line, reference line, event annotations, time axis, log y optional | `Chart` with doubled points, `rules`, no annotations | G1, G3, G4, G2 |
| 2. Cost by stage, stacked bars per circuit | categorical x, stacked segments, legend by stage, tooltips with share | `BarStrip` for one circuit; `Chart` bars are not stacked | G6, G4 |
| 3. Salt spread strip per promoted circuit | categorical x, jittered points, per-point pass/fail colour, optional box | `Chart` scatter with computed jitter | G4, G7 |
| 4. Pareto scatter, Toffolis against qubits, iso-cost curves | scatter plus several curves on different x, point labels, click to open the circuit, log axes | `Chart` scatter plus line series after an x union (G8) | G8, G2, G3, G5 |
| 5. Experiment funnel | four stages on one scale, drop-off percentages | `Progress` rows or horizontal bars | G6 |
| 6. Verify wall time per benchmark and host | grouped bars, or strip, log y | `Chart` bars (grouped, side by side) | G4, G2 |

## (b) Smallest general enhancement for each gap

Points use indah's 1 to 5 story scale: 1 is a day or less of work in one layer, 3 is a component
extension with a Studio page, tests and docs in both layers, 5 is a new component with its own
renderer. "Frontend" means Svelte work and a `make frontend` rebuild (the shell is committed).
Every item also needs the Studio page, `covers` entry and docs table that `STUDIO.md` requires; that
is included in the estimate.

### G1. Step series on Chart (1 point, frontend)

Every time-series of "best so far" wants it: leaderboard history, a benchmark's record cost, an
autoscaler's replica count. uPlot has `paths.stepped`.

```python
Chart(rows, series=[{"label": "score", "kind": "step", "align": "after"}])  # "after" | "before"
```

Extend `_SERIES_KINDS` (`components.py:1523`) and the switch at `Chart.svelte:42`.

### G2. Log scales on Chart (1 point, frontend)

```python
Chart(rows, x_scale="linear", y_scale="log")  # "linear" | "log"; log needs a positive range
```

uPlot supports `scales.y.distr = 3`. Validate in Python that `y_range` low is above zero and drop
or reject non-positive values. Needed for cost products spanning decades, wall time, and
any heavy-tailed benchmark in any indah app.

### G3. Chart annotations: vertical rules, bands, markers (2 points, frontend)

`rules` is horizontal only (`:1578`); `playhead` is a single x. General fix: let `rules` take `x`,
and add `bands` and `markers`, all drawn in the existing `drawOverlays` hook (`Chart.svelte:98`).

```python
rules = [{"y": 31, "label": "public best"}, {"x": 1763000000, "label": "v3 promoted", "dash": True}]
bands = [
    {"x0": 10, "x1": 40, "color": "var(--err)", "alpha": 0.12, "label": "fails gate"},
    {"y0": 0, "y1": 1.0},
]
markers = [{"x": 12, "y": 4.2, "label": "Q=300", "tone": "ok"}]
```

Same 12-item cap per list, same `_color` validation.

### G4. Time and category axes on Chart (2 points, frontend)

```python
Chart(rows, x_axis="time")  # x values are epoch seconds or ISO strings
Chart(rows, x_axis="category", x_labels=["invsqrt", "dqi", "dfthcsos"])
Chart(rows, y_labels=[...])  # optional, for lanes
```

Time uses uPlot's built-in time scale (`time: true`, currently hard-coded false at
`Chart.svelte:161`); category maps integer x to a label in a custom `axes[0].values` formatter.
Python converts ISO strings to epoch seconds in `_to_rows`.

### G5. Chart hover and click events back to Python (3 points, frontend)

Match what `Graph` already offers (`hovered`, `selected`, `components.py:2370`).

```python
picked = Signal[tuple[int, int] | None](None)  # (series index, row index)
Chart(rows, selected=picked, hovered=hovered, tooltip=True)
```

Frontend: a tooltip `div` from the `setCursor` hook, one debounced `hover` event (reuse Graph's
250 ms trailing debounce) and a `select` event on click. Opt in, as with Graph's `selectable`: no
signal, no events, so a display-only chart still sends nothing. Needed for "click a Pareto point to
open the circuit", and by any indah user wanting drill-down.

### G6. Stacked and horizontal bars (3 points, frontend)

```python
Chart(
    rows,
    series=[
        {"label": "mbuc", "kind": "bars", "stack": "cost"},
        {"label": "adders", "kind": "bars", "stack": "cost"},
    ],
    orientation="horizontal",
)  # a funnel is one stack-less horizontal series
```

uPlot has no native stacking; it is done by summing in the columnar builder and drawing each
series from its running base (about 40 lines in `Chart.svelte`). `orientation="horizontal"`
swaps the axes and needs a category axis (G4). Optional `normalize=True` for shares. Covers plots 2
and 5 and every "breakdown" in any app. G4 is a prerequisite.

### G7. Box (and strip) series (3 points, frontend)

Not violin: a strip plus a box answers "how spread are the salts" and a violin needs a kernel
estimate nobody will check.

```python
Chart(
    rows,
    x_axis="category",
    series=[
        {"label": "spread", "kind": "box"},  # row: [x, lo, q1, median, q3, hi]
        {"label": "salts", "kind": "scatter", "jitter": 0.18, "seed": 7},  # deterministic jitter
    ],
)
```

The box reads a six-number row, so the five-number summary is computed in Python
(`indah.box_stats(values)` helper, one line). `jitter` with a `seed` keeps Studio pages
deterministic. Needs G4.

### G8. Align helper for series on different x (1 point, Python only)

```python
rows = indah.chart_rows({"score": [(t0, 1.0), (t1, 1.2)], "frontier": [(t0, 1.5)]})
# -> [[t0, 1.0, 1.5], [t1, 1.2, None]]   sorted union of x, None where a series has no value
```

Pure Python next to `_to_rows`; no frontend change. Also normalise `NaN` and infinity to `None`
there (JSON cannot carry them; indah's `JsonTree` already uses `allow_nan=False` at `:4377`, so a
chart should refuse them the same way, clearly).

### G9. Spans component: flame, icicle, timeline and swimlane (5 points, frontend)

One component for "nested or laid-out intervals", which is a flame graph, an icicle, a Gantt and a
trace view. It is a general profiler and tracing view, useful for any indah app that shows
agent steps, request traces or training phases.

```python
Spans(
    spans,  # [{"id", "label", "start", "end"|"value", "parent"?, "lane"?, "color"?, "group"?}]
    mode="flame",  # "flame" | "icicle" | "timeline"
    selected=sig,
    hovered=sig,  # same contract as Graph
    zoom=True,  # click a span to zoom into it; breadcrumb to go back
    unit="Toffoli",  # tooltip text
    height="auto",
)
```

Render with canvas or absolutely positioned `div`s under the nonce CSP (no inline style attributes:
`style-src-attr 'unsafe-inline'` exists in `csp.py`, but follow what `Graph.svelte` does), lazily
loaded like `graph.js` so the shell does not grow. Columnar wire form like Graph. Cap on spans
(for us a kickmix circuit has tens of marks, not thousands). Timeline mode is the same layout with
`lane` rows, which also closes the experiments timeline.

### G10. Graph: directed edges, node and edge styles, layered layout (3 points, frontend + Python)

```python
Graph(
    nodes,
    edges,
    directed=True,
    layout="layered",  # "auto" | "given" | "layered"
    # node dict: {"id", "label", "group", "stroke": "dashed" | "solid" | "none", "shape": "circle"|"square"}
    # edge dict: {"source", "target", "dash": True}
)
```

Three small pieces. Arrowheads and dash are a few lines in the canvas drawing in `Graph.svelte`
(lazy module, about 1 to 2 KB more against the 16.9 KB limit). `layout="layered"` computes
left-to-right layers in the browser for a DAG and falls back to `auto` with a console warning on a
cycle; if that is too much, ship `indah.dag_layout(nodes, edges) -> nodes with x,y` as a Python
helper (1 point) and use `layout="given"`, which works today. The `shape` option is what makes
dashes non-colour-only; do both.

### G11. Sparkline and tick strip, usable in a table cell (3 points, frontend)

`BarStrip` shows the right idea but is a standalone component, and cells only accept a few
allowlisted tags (`protocol.py:115`) plus `Steps` (`StepsCell.svelte`). Follow the `Steps`
precedent: one new component with a cell binding.

```python
Sparkline(values, kind="line" | "bars" | "ticks", tones=["ok", "err"], height=24, label="cost by parent")
# in a table: Col("costs", kind="cell", render={"component": "sparkline", "bind": {"values": "costs"}})
```

`ticks` mode takes a list of values mapped to tones (`[0, 0, 1, 0]`, `names=["pass","fail"]`), so
the per-salt strip is one line and a failure has a shape (taller, or a cross) as well as a colour.
Also add `Stat(..., spark=[...])` as a one-line reuse. Cells must keep a fixed row height, so the
height is capped at 32 px.

### G12. Stat polish: direction and tone (1 point, frontend)

```python
Stat(value, label="Toffolis", delta="-12", delta_good="down", tone="ok")  # delta_good: "up" | "down" | "none"
```

Today the delta colour is decided by a leading `-` (`components.py:3126` docstring). Cost and
latency apps need the opposite sign convention. `tone` colours the value (for "worst salt: FAIL").

### G13. Slider: readout, marks, commit on release, log scale (2 points, frontend)

```python
Slider(
    value,
    min=1,
    max=4096,
    label="n",
    show_value=True,
    scale="log",
    marks=[{"value": 1024, "label": "cliff", "tone": "err"}],
    commit="release",
)  # "input" | "release"
```

`Node.svelte:681-697` renders a bare range input and posts every `input`. For a slider that drives a
cost model, `commit="release"` (post on `change`, keep a local readout while dragging) avoids
flooding the `/api/event` bucket; `marks` use the native `<datalist>` ticks; `scale="log"` maps
position to value in the frontend. The doc risk: do not break the default (every move posts).

## (c) Recommended order and what the Plot fallback buys us

The dashboard tabs do not all need the same amount of indah work. Rule: build the tab on what exists
now, ship, and let the gap list feed indah in parallel, so no tab waits.

**Priority order for indah work**

1. **G1, G2, G3, G8** (5 points total, mostly one file). They lift the Scoreboard and the Cost
   explorer, which are the two tabs that sell the story, and every one is a Chart feature any
   indah user would use. G8 is Python-only and can land first.
2. **G11 and G12** (4 points). The tick strip and sparklines are the Verifier theatre tab and
   make the Experiments table worth reading. The `BarStrip [1,0]/[0,1]` workaround covers the
   tick strip outside a table meanwhile.
3. **G10** (3 points). Lineage is the tab with the most distinct need (direction, dashed
   nodes), and the dash is a licence cue, not decoration. Colour-only is a real weakness.
4. **G4, G6, G7** (8 points together; G4 first). Stacked and horizontal bars, category axes and
   box series: these are the three static plots 2, 3, 5, 6. Highest cost, lowest urgency (the PNGs
   exist).
5. **G5** (3 points). Click and tooltip on a chart; the biggest single interactivity upgrade, but
   no tab is blocked without it.
6. **G13** (2 points). Useful; the explorer works without it (the label can hold the value).
7. **G9** (5 points). The flame chart is the most visually distinctive piece and the biggest cost.
   Do it last, after the cheaper Chart work has taught us the Studio, size-budget and CSP
   routine.

**What we can skip, or defer, using `Plot` as the interim fallback**

`Plot(fig)` (`components.py:1486`) shows a Matplotlib figure from the ledger, and `bench plots`
already produces them. For these, the PNG is an honest first version in the dashboard, with no
indah change:

- Plot 2 stacked bars (G6), plot 3 strip and box (G7, G4), plot 5 funnel (G6), plot 6 wall time
  (G4): all four are static summaries nobody needs to hover. Embed the figure; revisit after
  priority 1 to 3 land. A `Progress` column is a passable funnel without any figure.
- Plot 4 Pareto (G5, G8): PNG first, interactive once G5 exists.
- Anatomy flame chart (G9): show the SVG kickmix emits through `Image` with a `data:` URI, plus the
  stage table with `Progress` bars next to it. It is inert, so click-to-detail is lost until G9.
- Lineage (G10): ship with `Graph` as is, groups for kind (ours, public, baseline) and an explicit
  "no licence" group; add dashes when G10 lands. If layered layout is wanted before G10, compute
  `x`/`y` in Python and use `layout="given"`.
- Experiments sparklines (G11): leave them out of the first table; the table is useful without.

**Not skippable without a visible loss:** G1 plus G3 for the Scoreboard (staircase and the
frontier are the headline), and G2 for the Cost explorer (a product of three factors is unreadable
on a linear axis). Both are cheap. Staircase has a hack (doubled points); log has only a
`log10`-transform hack that makes the tooltip values wrong, so prefer waiting for G2.

**Own module as a last resort.** `register_component(module=...)` (`custom.py:123`) lets us ship an
ES module of our own for the flame chart, with no indah change. It cannot sit in a table cell
(documented limit) and counts against the 1 MB and 64-module caps. It is the right route only if
indah's side is late; the owner's direction is to improve indah instead.

## (d) Risks

**Bundle size** (`docs/size-budget.json`). Measured on the checked-in shell: `index.html` is
472,203 bytes raw and 213,534 bytes gzip against budgets of 495,000 and 231,000. That is about 22 KB
raw and 17 KB gzip of room for the whole shell, and the budget comment says each limit is already 15
percent above the last measurement. G1, G2, G3, G4, G5, G11, G12 and G13 all live in the shell; as
estimates, G1, G2, G12 are under 1 KB, G3, G4, G13 are 1 to 2 KB, G5, G6, G7, G11 are 2 to 4 KB.
Together they could use most of the headroom, so make a decision in indah before starting: a bigger
shell budget, or move the larger additions (G7, G9, parts of G6) into a lazy module like `graph.js`
(which has its own budget entry, `graph_raw_bytes: 16900`). G9 must be lazy. Also check
`python_source_bytes` (limit 600,000): `components.py` is 5,167 lines, and every component adds
validation code.

**CSP strict mode.** The whole e2e suite runs under `csp="strict"` and fails on any violation. No
inline styles, no `eval`, no external images or fonts. Canvas drawing and `div`s styled through
classes or CSSOM are fine; anything a component needs from `style=` attributes has to follow what
the existing components do. Colours must go through `_color` (`components.py:1523`), which rejects
`url(` and `expression`, and a string such as `var(--err)` is what makes themes work. Any text from
our ledger (hypotheses, hashes) that goes into labels or tooltips must be set as text, never HTML.
Custom module components (our fallback) need the nonce on any `<style>`, documented at
`website/docs/custom-components.md`.

**Patch size for large series.** Reactive `data` replaces the whole prop on each change; only
`push`/`extend` send deltas (`session.py:202`, `emit_append`). A slider that recomputes a chart
sends the full series on every committed value. For our scale this is small (a few hundred rows for
the cost explorer, tens of thousands for a full ledger at the extreme), and `max_event_bytes` is
1 MiB for a POST body, not for outbound patches. Still: (1) keep the explorer at 200 points or
fewer; (2) G13's `commit="release"` matters more than it looks, because per-move recompute plus a
full-prop patch is the expensive path; (3) the experiments table must use `Table(remote)` or
paging, not a thousand rows in one patch; (4) the flame chart (G9) should send columnar spans with
integer parent indexes, like Graph's edges, not nested JSON. Graph caps nodes at 10,000 by default;
a lineage graph of ours is tens of nodes, so no issue.

**Other.**
- **Local-first.** The dashboard reads `ledger/` and is not hosted (ADR-0008 D3). That makes
  waiting for indah releases cheap: we pin an indah version from PyPI as an optional extra and
  upgrade when a gap lands. We do not need anything unreleased to ship a first dashboard.
- **Release coupling.** Gaps land in indah on their schedule and the owner controls both; do not
  start a tab that depends on a gap until the gap has a version number on PyPI, or use the
  fallback and swap later.
- **Unverified claims.** The `data:` SVG in `Image` and the `Progress` funnel were read from code,
  not run. Check both in a Studio page (`make demo`) before the dashboard story relies on them.
  `Slider` readout and `Graph` arrow absence are confirmed by reading `Node.svelte` and `Graph.svelte`.
- **Accessibility.** Indah keeps a rule that colour is never the only cue (`Steps`, `BarStrip`).
  Our dashed-node and pass/fail tick needs (G10, G11) are exactly where that rule bites, so those
  two should ship with a shape cue, not just a tone.
