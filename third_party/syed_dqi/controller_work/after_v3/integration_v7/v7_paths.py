# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Fixed source roots for the next T-only continuation; no profile inputs."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
WORK = PROJECT.parent
ROOT = WORK.parent


def enable_new_sources():
    for path in (PROJECT/'blocks', PROJECT/'k24', PROJECT/'scan',
                 PROJECT/'audit/retained_child', PROJECT/'blocks/v5',
                 PROJECT/'k24/v5_transpose14', PROJECT/'blocks/v5_cubic_phase20',
                 PROJECT/'blocks/v6', PROJECT/'k24/adaptive_gauge'):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))


# The immutable accepted loader establishes its native import boundary first.
if str(PROJECT/'blocks') not in sys.path:
    sys.path.insert(0, str(PROJECT/'blocks'))
