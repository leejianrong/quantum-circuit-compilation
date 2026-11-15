# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Paths for isolated post-v3 arithmetic work; no production mutation."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[1]
for path in (WORK/'after_c5/arithmetic_t', WORK/'night_c27/arithmetic'):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
import c27_paths  # noqa: E402,F401
