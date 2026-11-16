# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Isolated post-C5 converter-width experiment paths; no baseline edits."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[1]
for directory in (WORK / 'work/round2/milestone152/source',
                  WORK.parent / 'pro1_controller_bundle/1_task/official',
                  WORK / 'night_schedule', WORK / 'night_converter',
                  WORK / 'night_c27/arithmetic'):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

