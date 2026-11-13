# Notice

This directory holds files from the repository andigu/uncompute on GitHub (Andi Gu, Alek H. Kemeny, Susanne F. Yelin,
Mikhail D. Lukin; arXiv:2610.22367), commit `64b5a13aa249f1360846657392e6c66817b26d0f`, licensed under the
Apache License 2.0 (see `LICENSE`).

Vendored files, unmodified: `builder.py`, `bennett.py`, `classical.py`, `compact.py`, `ops.py`, `gadgets/*.py`.
Modified: `__init__.py` (the `Simulator` import and its exports were removed; the simulator, evaluator, C kernels
and the `testing` helpers are not vendored).

Used by `src/dqi_gen/rs/` (the port of the upstream `dqi-reed-solomon` discovered circuit); see
`THIRD_PARTY_NOTICES.md` at the repository root for what that port changes.
