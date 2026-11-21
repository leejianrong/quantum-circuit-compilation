# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0. Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.
"""Rebuild the parent from native sources and apply the frozen staged transform."""
from pathlib import Path
import sys
from build64_conditional_early_q import main as parent_main
import temporal_q35_q9_native_v1
if __name__ == "__main__":
    parent_main()
    temporal_q35_q9_native_v1.apply(Path(sys.argv[sys.argv.index("--out")+1]))
