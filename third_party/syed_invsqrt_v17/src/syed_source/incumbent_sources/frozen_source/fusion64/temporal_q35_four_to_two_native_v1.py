# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Compose the qualified native chain and the two-time q35 four-to-two merge."""
from pathlib import Path


def apply(raw_directory):
    import hmr_q8_advance_native_v1
    import q35_four_to_two_native_v1
    raw_directory=Path(raw_directory)
    hmr_q8_advance_native_v1.apply(raw_directory)
    return q35_four_to_two_native_v1.apply(raw_directory)
