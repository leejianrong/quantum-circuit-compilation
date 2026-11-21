# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0
# Credits: Opus and Astra.
"""Paper-authorized Q48 composition with a new, independently checked phase."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import sys

for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'

HERE = Path(__file__).resolve().parent
NARROW = HERE.parents[1]
BASE = HERE.parent / 'candidate01'
PREVIOUS = HERE.parent / 'candidate06'
GATE_PATH = NARROW / 'PAPER_GATE_RECEIPT_022_VARIANT.json'
GATE_SHA = 'f8cfe4331b37a5184a4aab17ee85b4ac892c08c2cfb863fc4b1c1b3c9978262e'
PAPER_SHA = '49ce6e7007b19abcd533b82a9f291b617cbc1c864a3d66287c0e63a87ebb82c4'
PHASE_GATE_SHA = 'b579924175ee8e73c61c2f945b2d85e8ba2e536a8dbd8288a8332628142cd569'


def verify_inputs():
    for pin in json.loads((HERE / 'INPUTS.json').read_text())['files']:
        raw = (NARROW / pin['path']).read_bytes()
        assert len(raw) == pin['bytes'], pin['path']
        assert hashlib.sha256(raw).hexdigest() == pin['sha256'], pin['path']


verify_inputs()
spec = importlib.util.spec_from_file_location('candidate07_pinned_candidate06_variant', PREVIOUS / 'variant.py')
previous = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = previous
spec.loader.exec_module(previous)
common = previous.common
divider = previous.divider
ACCEPTED = common.checked_json(GATE_PATH, GATE_SHA)
PAPER = common.checked_json(NARROW / ACCEPTED['paper_gate_path'], PAPER_SHA)
PHASE_GATE = common.checked_json(NARROW / PAPER['phase_gate_path'], PHASE_GATE_SHA)
NEW_TURN_UNITS50 = tuple(PAPER['new_angles_turn_units50'])
SITES = tuple(PAPER['phase_site_order'])
assert ACCEPTED['native_build_authorized']
assert ACCEPTED['all_native_candidates_preserved'] == [1, 2, 3, 4, 5, 6]
_INSTALLED = False
MODULES = {}


def accuracy_receipt():
    """The new ring26 receipt; never substitute the old27 quantization data."""
    digest = PAPER['accuracy_receipt_sha256']
    result = common.checked_json(NARROW / PAPER['accuracy_receipt_path'], digest)
    exact = result['exact_screen']
    stats = exact['statistics']['grid50']
    assert result['status'] == 'COMPLETE_EXACT_RING26_PAPER_GATE_NATIVE_PENDING'
    assert stats['inputs'] == 3133452 and stats['failures'] == 0
    assert stats['minimum_margin_units'] == 124370688
    assert exact['phase50_sha256'] == PAPER['independent_phase_units50_sha256']
    assert exact['direct_and_baseline_plus_delta_agree'] and exact['original_tolerance_unchanged']
    assert result['original_tolerance_unchanged'] and result['accuracy_decisions_integer']
    assert tuple(result['new_angles_units50']) == NEW_TURN_UNITS50
    assert NEW_TURN_UNITS50[-1] == 0 and any(x & 1 for x in NEW_TURN_UNITS50)
    return result, digest


def variant_gate():
    verify_inputs()
    accuracy, digest = accuracy_receipt()
    assert PAPER['Q'] == 48 and PAPER['expected_Toffolis'] == 1584
    assert PAPER['T'] == 4 and PAPER['R'] == 33
    assert sum(PAPER['components_expected_Toffolis'].values()) == 1584
    assert max(row['live'] for row in PAPER['owner_cuts']) == 48
    assert PAPER['full_lifecycle_E'] == 562 and PAPER['nonproduct_lifecycle_E'] == 321.5
    assert PAPER['first_preparation_peak'] == PAPER['second_preparation_peak'] == PAPER['endpoint_peak'] == 48
    assert PAPER['rotation_charge'] == accuracy['complete_paper_gate']['rotation_charge']
    assert PAPER['unchanged_original_tolerance'] and PAPER['new_oracle_required']
    assert PHASE_GATE['expected_Toffolis'] == 1585
    assert PHASE_GATE['phase_expected_Toffolis'] == 139
    assert tuple(PHASE_GATE['new_angles_turn_units50']) == NEW_TURN_UNITS50
    assert PHASE_GATE['zero_new_deferred_phase_debts_at_endpoint_exit']
    return dict(status='ACCEPTED_COMPLETE_Q48_RING26_GATE_NEW_NATIVE_PROOF_REQUIRED',
                Q=48, Toffolis_expected=1584, T=4, R=33,
                rotation_charge=PAPER['rotation_charge'], total_E=PAPER['total_E'],
                paper_cost=PAPER['complete_expected_cost'],
                complete_components=PAPER['components_expected_Toffolis'],
                first_loader_peak=48, second_loader_peak=48, endpoint_peak=48,
                accuracy_receipt_sha256=digest,
                exact_minimum_margin_units64=124370688,
                independent_phase_units50_sha256=PAPER['independent_phase_units50_sha256'])


def local_module(name):
    if name not in MODULES:
        path = HERE / (name + '.py')
        if name in sys.modules:
            module = sys.modules[name]
            assert Path(module.__file__).resolve() == path.resolve()
        else:
            spec = importlib.util.spec_from_file_location('candidate07_' + name, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            sys.modules[name] = module
            spec.loader.exec_module(module)
        MODULES[name] = module
    return MODULES[name]


def install():
    global _INSTALLED
    variant_gate()
    if not _INSTALLED:
        previous.install()
        local_module('phase07').install(previous, NEW_TURN_UNITS50, PHASE_GATE)
        _INSTALLED = True
    return divider


def load_baseline(name):
    return previous.load_baseline(name)


def inherited_module(name):
    """Keep the old module/class identity while reusing its arithmetic only."""
    return previous.local_module(name)
