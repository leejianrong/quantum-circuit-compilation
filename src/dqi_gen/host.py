"""Load kickmix and the host's DQI verifier from the competition data directory.

The host files under ``data/verifiers/dqi`` are Apache-2.0 reference code. They are read, never edited.
"""

from __future__ import annotations

import importlib
import os
import pathlib
import sys
from types import ModuleType


def data_dir() -> pathlib.Path:
    return pathlib.Path(os.environ.get("QCC_DATA", "data"))


def verifier() -> ModuleType:
    """The host verifier module (``verify_submission_dqi``)."""
    data = data_dir()
    for p in (data / "kickmix", data / "verifiers"):
        if str(p) not in sys.path:
            sys.path.append(str(p))
    return importlib.import_module("dqi.verify_submission_dqi")


def reference() -> ModuleType:
    """The host reference builder module (``dqi_reference_circuit``)."""
    verifier()
    return importlib.import_module("dqi.dqi_reference_circuit")
