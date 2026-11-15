# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Read-only imports of the completed C5 reference from this isolated branch."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[1]
for directory in (WORK / 'night_c27/arithmetic',
                  WORK / 'night_c27/controller',
                  WORK / 'night_c27/census'):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
import c27_paths  # noqa: E402,F401
