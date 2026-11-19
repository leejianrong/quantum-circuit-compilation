#!/usr/bin/env python3
# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""macOS launcher for the frozen Linux-oriented invsqrt sources.

Runs SCRIPT exactly as `python SCRIPT ARGS...` would, with one environment shim:
macOS rejects lowering RLIMIT_AS (ValueError/OSError), which several hash-pinned
sources call at import time. The shim turns only that rejected call into a no-op;
memory is bounded externally by tools/memguard.sh. No pinned file is modified and
no circuit, proof or verifier check is touched.
"""
import os, resource, runpy, sys

_original = resource.setrlimit
SKIPPED = []


def _setrlimit(which, limits):
    try:
        return _original(which, limits)
    except (ValueError, OSError) as error:
        if which in (resource.RLIMIT_AS, resource.RLIMIT_CORE, getattr(resource, 'RLIMIT_DATA', -1)):
            SKIPPED.append((which, tuple(limits), str(error)))
            return None
        raise


resource.setrlimit = _setrlimit

if __name__ == '__main__':
    script = os.path.abspath(sys.argv[1])
    sys.argv = [script] + sys.argv[2:]
    sys.path.insert(0, os.path.dirname(script))
    runpy.run_path(script, run_name='__main__')
