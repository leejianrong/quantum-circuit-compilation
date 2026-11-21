# Copyright2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Authorized AR004 cleanup-only adapter; forward and phase stay unchanged."""
from pathlib import Path
import hashlib, importlib.util, json, sys

HERE = Path(__file__).resolve().parent
NARROW = HERE.parents[3]
KERNEL = HERE.parent/'history12_kernel.py'
KERNEL_SHA = '1dc5022918a0a47663ec3ad812cdff67f93ee0c1646f3e4db59ee7881c847afe'
TOP_KERNEL = HERE.parent/'top12_kernel.py'
TOP_KERNEL_SHA = 'f4367db957bac36fc319389358984ecf00b6b8788b7e19894f0600cf1e68aec5'
ACCEPTANCE = NARROW/'arithmetic_round2/receipts/DIVIDER_HISTORY12_PAPER_ACCEPTED.json'
ACCEPTANCE_SHA = 'd188e0b75ffa397879884f4d77c64fa409b4cada180e5253244f415d84e1d8e7'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify():
    assert sha(ACCEPTANCE) == ACCEPTANCE_SHA
    assert json.loads(ACCEPTANCE.read_text())['native_build_authorized'] is True
    assert sha(KERNEL) == KERNEL_SHA and sha(TOP_KERNEL) == TOP_KERNEL_SHA
    for pin in json.loads((HERE/'INPUTS.json').read_text())['files']:
        path = NARROW/pin['path']
        assert path.stat().st_size == pin['bytes'] and sha(path) == pin['sha256'], pin['path']


def load(name, path):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    module = sys.modules[name]
    assert Path(module.__file__).resolve() == path.resolve()
    return module


def kernel():
    verify()
    base = load('top12_kernel', TOP_KERNEL)
    result = load('_ar004_frozen_history12_kernel', KERNEL)
    assert result.base is base
    return result


def bind(divider):
    verify()
    assert Path(divider.__file__).resolve() == (NARROW/'native/candidate01/divider.py').resolve()
    assert Path(divider.initialize_u12.__code__.co_filename).resolve() == (NARROW/'native/candidate02/variant.py').resolve()
    assert Path(divider.inverse_add.__code__.co_filename).resolve() == (NARROW/'checkpoint002/cleanroom/baseline_stage97/engine/paired_arithmetic.py').resolve()
    implementation = kernel()
    def cleanup(builder, token):
        return implementation.cleanup_divider(divider, builder, token)
    return cleanup


def install(divider):
    forward, phase, initializer = divider.compute_divider, divider.phase_endpoint, divider.initialize_u12
    divider.cleanup_divider = bind(divider)
    assert divider.compute_divider is forward and divider.phase_endpoint is phase
    assert divider.initialize_u12 is initializer
    return divider


CONTRACT = dict(Q=48, divider_E=578.0, T=0, R=0, forward_unchanged=True,
    endpoint43_unchanged=True, inverse42_until_history13_restored=True,
    entry_and_return_owners=31, all24_carry_debts_required=True,
    returns_current_P15=True, only_frozen_model_original_domain_claimed=True)
