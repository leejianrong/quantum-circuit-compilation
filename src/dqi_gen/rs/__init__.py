"""Port of the upstream `dqi-reed-solomon` discovered circuit (Gu, Kemeny, Yelin, Lukin; Apache-2.0).

Importing this package puts the vendored `third_party/uncompute` on `sys.path` (it is imported as `uncompute`).
See `THIRD_PARTY_NOTICES.md` and `third_party/uncompute/NOTICE.md`.
"""

import pathlib
import sys

_TP = str(pathlib.Path(__file__).resolve().parents[3] / "third_party")
if _TP not in sys.path:
    sys.path.insert(0, _TP)
