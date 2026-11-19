# Vendored from syed3000's invsqrt builder (Apache-2.0)

Source: Kaggle dataset `syed3000/vqcc-own-circuit-portfolio` version 12, file `invsqrt_source_zip` (Copyright 2026 Syed Asad Ali,
licensed under Apache-2.0, see `LICENSE` and `NOTICE` here; credits named by the authors: Syed Asad Ali, working with a team of AI
agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research). The
NOTICE asks that every redistribution and every derivative carry it and name Syed Asad Ali as the original builder.

Files: the 78 Python files that a sandboxed build of the 46-qubit circuit (`321aff83...`) executes, found by tracing the build with an
audit hook (`docs/experiments/invsqrt-port-plan.md`, Stage B; the list is `docs/experiments/data/invsqrt_v12_executed_py.txt`).
They are copied byte for byte with their original path layout under `src/` and their own headers. Nothing here is modified:
`MANIFEST.sha256` lists their SHA-256 values, which equal the archive's own `SHA256SUMS`, and `tests/unit/test_vendored_invsqrt.py`
checks them.

Not vendored: the 302 data files the build opens (JSON certificates, pinned reference circuits, 16 MB; they stay in the
downloaded archive under `public/`), the shell steps (`build.sh`, `tools/pipeline.sh`) and the other 177 Python files of the
archive (research code the build never executes).

Provenance statements: the dataset README says the builders are original work and names no other ancestor. Recorded in
`docs/PROVENANCE.md` and `THIRD_PARTY_NOTICES.md`.
