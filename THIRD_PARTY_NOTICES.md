# Third-party notices

Code or circuits ported into this repository from other projects. Each entry names the source, the commit,
the licence, what we took and what we changed. Add an entry in the same PR as the port.

| Source | Commit | Licence | Files ported | Changes |
|---|---|---|---|---|
| https://github.com/andigu/uncompute (Gu, Kemeny, Yelin, Lukin; arXiv:2610.22367) | `64b5a13aa249f1360846657392e6c66817b26d0f` (studied 2026-11-13, read-only) | Apache-2.0 | none ported: the `coulomb-potential` task is a different instance (see `docs/research/uncompute-coulomb.md`) | none |
| https://www.kaggle.com/datasets/syed3000/vqcc-own-circuit-portfolio (Syed Asad Ali, v12; Apache-2.0 per the dataset metadata and its LICENSE file, copyright 2026 Syed Asad Ali) | dataset v12 | Apache-2.0 | `invsqrt.kmb` (sha256 `321aff83636214196daa9cbc9dcc9c5e12a155bcff8d9989e98b8cee40935177`), used unmodified as a candidate circuit and verified with the official verifier; kept outside the repository at `~/qcc-circuits/invsqrt/` together with the LICENSE; not committed, not in `best/` | none (byte-identical); the other files of the dataset (DQI, chemistry, builder sources) were not loaded or used |
