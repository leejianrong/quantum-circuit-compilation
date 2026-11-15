# Environment

Where the work runs, with what, and what lives outside git. The step-by-step setup and the full table of
non-git assets are in [HANDOFF](../HANDOFF.md); this page is the stable summary. No credentials appear here.

## Machines

| Machine | Resources | Used for |
|---|---|---|
| Original machine (WSL2) | 7 GB RAM, 16 cores, shared | the work before the 2026-11-14 restore; one heavy verify at a time under `flock /tmp/qcc-heavy.lock` |
| Second machine (WSL2) | RTX 3080 Ti (16 GB), 20 cores, 31 GB RAM | restored 2026-11-14; the 7 GB limit does not apply, but keep one heavy verify at a time |
| Kaggle kernels | free CPU, weekly GPU quota | full-size DQI builds and verifies (5 to 9 GB), the dfthcsos fits (6 to 20 hours each) |
| Rootless container (local image, glibc 2.39) | no network, inputs read-only | running the competition `kickmix.so`, which needs a newer libstdc++ than the WSL hosts have |

## Software

* CPython 3.12 or newer; `uv sync` picks the newest (3.14 on the second machine) and `make check` passes.
* kickmix: always the pip wheel from `uv sync`. Never put `data/kickmix` on `sys.path` ahead of it.
* torch is installed by hand in the second machine's `.venv` (not a project dependency); its CUDA initialisation
  segfaults there, so pushes use `CUDA_VISIBLE_DEVICES=`. A plain `uv sync` removes torch: use
  `uv sync --inexact --extra <name>`.
* Extras: `plots` (matplotlib, used by the figures and the docs CI), `dashboard` (indah), `shots` (Playwright).
* The docs site is Zensical 0.1; MathJax is vendored; Mermaid is loaded from a CDN at view time.

## Outside git

`data/` (competition data, never redistributed), `public/` (third-party circuits, licences as stated), `best/`,
`out/`, `~/qcc-circuits/` (our built circuits), `~/qcc-fits/` (dfthcsos fits and Kaggle outputs). Where each came
from and how to regenerate it is in [HANDOFF](../HANDOFF.md).

## Verifying

Official verifier only for anything that gates promotion; reduced-shot and `kickmix-engine` runs are screening
(`kind=screen`). `bench verify invsqrt` takes about 5 minutes per salt on all cores. See
[measurement](../MEASUREMENT.md).
