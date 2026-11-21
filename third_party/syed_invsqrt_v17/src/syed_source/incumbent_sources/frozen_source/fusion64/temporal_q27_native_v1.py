# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Rebuild the qualified later-q28 merge, then apply only the q27 merge."""
from pathlib import Path


def apply(raw_directory):
    import distributive_q28_native_v1
    import q27_temporal_merge_native_v1
    raw_directory = Path(raw_directory)
    distributive_q28_native_v1.apply(raw_directory)
    return q27_temporal_merge_native_v1.apply(raw_directory)
