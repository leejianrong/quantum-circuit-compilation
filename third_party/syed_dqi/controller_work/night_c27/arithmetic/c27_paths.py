# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Paths for the isolated C2.7 arithmetic implementation."""
from pathlib import Path
import sys

WORK = Path(__file__).resolve().parents[2]
for directory in (WORK / 'work/round2/milestone152/source',
                  WORK.parent / 'pro1_controller_bundle/1_task/official',
                  WORK / 'night_schedule', WORK / 'night_root',
                  WORK / 'night_c27/controller'):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
