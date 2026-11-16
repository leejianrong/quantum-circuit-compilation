# Vendored from syed3000's DQI builder (Apache-2.0)

Source: Kaggle dataset `syed3000/vqcc-own-circuit-portfolio`, file `dqi_source_zip` (Copyright 2026 Syed Asad Ali, licensed
under Apache-2.0, see `LICENSE` and `NOTICE` here; credits named by the authors: Syed Asad Ali, working with a team of AI agents
(GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research).

Files: 99 Python modules (58 first, 16 added 2026-11-16 and 25 more the same day, QCC-19 stage 2: the back half of the newer pipeline, namely the infinity-3 finish `projective_finish_infinity3`, `zero_mask_scan`, `adaptive_gauge64`, the transpose14 outer (`transpose14_core`, `transpose14_window`, `transpose_handoff_*`, `window_transpose_handoff`), the gauge-park lenders, `paired_phase62`, `quotient_phase62`, `rolling_tail_deferred`, `scalar_seed_padded`, and their helpers; the 16 were: the closure of the three-pivot extractor adapter `first3_retained_norm_adapter`, `direct_carry_*`, `rolling_tail_early`, `gf24_nested_norm`, `nested_norm_inverse`, `last_return_retained_norm`, `quotient_phase84_mask_guard`; `after_c5/release_v3/normalized/direct_carry_first2.py` is not vendored, its only difference from `after_c5/extractor_width/direct_carry_first2.py` is a docstring wording) under `controller_work/` (the import closure of `raw_query_extractor`, `gf24_arithmetic`, `night_outer`, `projective_finish`, `additive_fft_phase_scan`, `mask_gauge_blocked`,
`rolling_tail`, `scalar_seed` and `fused_crt_synthesis`), copied byte for byte with their original path layout and their own
copyright and licence headers. Nothing in this directory is modified.

Provenance statements: the dataset's README says the builders are "100% original" and name no other ancestor. Third-party credit
texts in other Kaggle datasets (for example kirilltym's `SAMANYU2_CREDITS.md`) say that the 892-qubit DQI lineage rests on
jday96314's continued-fraction decoder (no licence stated, repository no longer reachable), SomeJoint's kit (Apache-2.0) and Ali
Haydar Ozdag's flag-carry idea; whether the 889-qubit package derives from that lineage is not stated in the package itself.
Recorded in `docs/PROVENANCE.md`; see `THIRD_PARTY_NOTICES.md`.
