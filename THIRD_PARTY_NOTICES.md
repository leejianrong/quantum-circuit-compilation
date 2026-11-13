# Third-party notices

Code or circuits ported into this repository from other projects. Each entry names the source, the commit,
the licence, what we took and what we changed. Add an entry in the same PR as the port.

| Source | Commit | Licence | Files ported | Changes |
|---|---|---|---|---|
| https://github.com/andigu/uncompute (Gu, Kemeny, Yelin, Lukin; arXiv:2610.22367) | `64b5a13aa249f1360846657392e6c66817b26d0f` | Apache-2.0 | `third_party/uncompute/` (`builder.py`, `bennett.py`, `classical.py`, `compact.py`, `ops.py`, `gadgets/*.py` unmodified, `__init__.py` modified, LICENSE, NOTICE.md); `src/dqi_gen/rs/circuit.py` and `constants.json` from `tasks/dqi-reed-solomon/circuits/discovered/`, `contract.json` (subset) from `tasks/dqi-reed-solomon/` | `circuit.py`: local helpers instead of `uncompute.testing`; fixed mask removed (runtime mask bits, no zlin, no skipped points); field-isomorphism stage (modulus 4179 to 4331) and its inverse; flat sweep with bit-conditioned pairing rows for the first `m` positions; header states the changes. `constants.json` unchanged. New original files: `src/dqi_gen/uc2km.py` (op stream to kickmix converter), `src/dqi_gen/rs_build.py`. |
