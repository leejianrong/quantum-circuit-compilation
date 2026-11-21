# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Compose the current qualified native transforms and causal q8 HMR advance."""
from pathlib import Path


def apply(raw_directory):
    import temporal_q27_pairA_native_v1
    import q21_advance_hmr_native_v1
    raw_directory=Path(raw_directory)
    temporal_q27_pairA_native_v1.apply(raw_directory)
    return q21_advance_hmr_native_v1.apply(raw_directory)
