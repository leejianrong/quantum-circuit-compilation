# Vendored from syed3000's v17 invsqrt generator (Apache-2.0)

Source: Kaggle dataset `syed3000/vqcc-own-circuit-portfolio` (v17, "a 28.71 stack", fetched 2026-11-21), directory
`invsqrt_generator/invsqrt_generator` (Copyright 2026 Syed Asad Ali, licensed under Apache-2.0, see `LICENSE` and `NOTICE` here;
credits named by the authors: Syed Asad Ali, working with a team of AI agents). The NOTICE asks that every redistribution and every
derivative carry it and name Syed Asad Ali as the original builder.

Files: the 220 Python files that a sandboxed build of the 43-qubit circuit (`70fe5f79...`) executes: 42 builder files at the top of the
generator (`build.py`, `owner_lineage.py`, `finish_f16.py`, the lineage and hand-cut modules) and 178 stage modules under
`syed_source/` (`docs/experiments/data/invsqrt_v17_executed_py.txt`, log `2026-11-21-invsqrt-v17-reference-build`). They are copied
byte for byte from the download, with their original relative paths under `src/`. `build.py` rewrites historical absolute paths in 21
of the stage modules at build time; the copies here are the files as shipped, before that rewrite. `MANIFEST.sha256` lists SHA-256
values and `tests/unit/test_vendored_invsqrt_v17.py` checks them.

Not vendored: the data files and certificates the build reads (they stay in the download under `public/`), `sitecustomize.py` (a macOS
memory shim; the sandbox build appended a trace hook to its copy), and the remaining Python files of the tree (search and research
code the build never executes).

Provenance statements: the dataset README says the generators are the authors' own work and names no other ancestor. Recorded in
`docs/PROVENANCE.md` and `THIRD_PARTY_NOTICES.md`.
