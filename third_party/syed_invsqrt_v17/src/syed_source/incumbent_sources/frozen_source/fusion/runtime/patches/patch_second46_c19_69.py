# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""LOADER2 pinned copy (made like agents/composer/mkpin.py) of agents/tk_q46/p/patch_second_q46.py: SECOND table load from the work-cap-19 second_framed
certificate tk46_second_framed_c19_b9_seed510016.json (SHA-256 c49ee950df9d2bb3ecc80e97a0f7dce7b25094fa5cab796bab7f14a6d6842bd5), emitted by q46_loaders.py (cap-aware copy of the lead's q47_loaders_lead.py).
The certificate path is forced (environment ignored) and hash-checked. Replaces only tables07.load_joint16 for
variant='second'.
"""
from pathlib import Path
import hashlib, importlib.util, os, sys

HERE = Path(__file__).resolve().parent
LOADERS = HERE / 'q46_loaders.py'
if not LOADERS.exists():
    LOADERS = Path('/Users/asad.ali/codex quantum/fusion3_reduced_anchor/reference_build/incumbent_sources/frozen_source/fusion/runtime/agents/tk_q46/p/q46_loaders.py')
CERT = '/Users/asad.ali/codex quantum/fusion3_reduced_anchor/reference_build/incumbent_sources/frozen_source/fusion/runtime/tools/tk/second_cap19_69_tail11_s9000.json'
CERT_SHA256 = '81b36218845b8cbd70596c63b6d9377d8b2c7920f3923439eb63309017b16f32'
REPORT = {}


def apply(ctx):
    assert hashlib.sha256(Path(CERT).read_bytes()).hexdigest() == CERT_SHA256
    os.environ['TK46_SECOND_JSON'] = CERT
    REPORT['certificate'] = CERT
    REPORT['certificate_sha256'] = CERT_SHA256
    name = 'tk46_q46_second_loader'
    assert name not in sys.modules
    spec = importlib.util.spec_from_file_location(name, LOADERS)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    assert str(module.OWN_SECOND) == CERT
    tables = ctx.tables
    adapted = module.adapter(tables)
    original = tables.load_joint16

    def load_joint16(builder, address7, *, variant, debts):
        if variant == 'second':
            return adapted.load_joint16(builder, address7, variant='second', debts=debts)
        return original(builder, address7, variant=variant, debts=debts)
    tables.load_joint16 = load_joint16
