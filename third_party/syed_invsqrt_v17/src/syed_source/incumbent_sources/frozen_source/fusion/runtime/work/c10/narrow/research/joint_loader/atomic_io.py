# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0
# Credits: Opus and Astra.
"""Atomic branch artifacts so an overlapping parent checkpoint is coherent."""
import os
from pathlib import Path


def atomic_text(path, text):
    path = Path(path)
    temporary = path.with_name('.' + path.name + '.tmp.' + str(os.getpid()))
    temporary.write_text(text)
    os.replace(temporary, path)
