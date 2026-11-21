# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0
# Credits: Opus and Astra.
"""Isolated, paper-authorized Q48 composition on immutable native sources."""
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
PREVIOUS = HERE.parent / 'candidate05'
GATE_PATH = NARROW / 'PAPER_GATE_RECEIPT_018_VARIANT.json'
GATE_SHA = '99ef9a891d4e99b262b1a452ea48b18c536e91e7017f018b77bc37f1793ccffd'
PAPER_SHA = '912da9164095aa996317909903d50162a76eded7ff9a90cbb9299c85c013de2c'


def verify_inputs():
    manifest = json.loads((HERE / 'INPUTS.json').read_text())
    for pin in manifest['files']:
        raw = (NARROW / pin['path']).read_bytes()
        assert len(raw) == pin['bytes']
        assert hashlib.sha256(raw).hexdigest() == pin['sha256'], pin['path']


verify_inputs()
spec = importlib.util.spec_from_file_location('candidate06_pinned_candidate05_variant', PREVIOUS / 'variant.py')
previous = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = previous
spec.loader.exec_module(previous)
common = previous.common
divider = previous.divider
BOUND = previous.BOUND
COEFFICIENTS37 = previous.COEFFICIENTS37
NEW_TURN_UNITS50 = previous.NEW_TURN_UNITS50
SITES = previous.SITES
ACCEPTED = common.checked_json(GATE_PATH, GATE_SHA)
PAPER = common.checked_json(NARROW / ACCEPTED['paper_gate_path'], PAPER_SHA)
assert ACCEPTED['native_build_authorized'] and ACCEPTED['all_native_candidates_preserved'] == [1, 2, 3, 4, 5]
_INSTALLED = False
MODULES = {}


def checked_quantized():
    result, digest = previous.checked_quantized()
    assert result['exact_statistics']['quantized50']['minimum_margin_units'] == 124372027
    assert result['new_generic_turn_units50'] == list(NEW_TURN_UNITS50)
    return result, digest


def variant_gate():
    verify_inputs()
    quantized, digest = checked_quantized()
    assert PAPER['Q'] == 48 and PAPER['expected_Toffolis'] == 1591
    assert PAPER['T'] == 4 and PAPER['R'] == 34
    assert sum(PAPER['components_expected_Toffolis'].values()) == 1591
    assert max(row['live'] for row in PAPER['owner_cuts']) == 48
    assert PAPER['rotation_charge'] == quantized['rotation_charge']
    assert PAPER['unchanged_original_tolerance'] and PAPER['unchanged_exact_integer50_phase_model']
    return dict(status='ACCEPTED_COMPLETE_Q48_GATE_NATIVE_PROOF_REQUIRED',
                Q=48, Toffolis_expected=1591, T=4, R=34,
                rotation_charge=PAPER['rotation_charge'],
                total_E=PAPER['total_E'], paper_cost=PAPER['complete_expected_cost'],
                complete_components=PAPER['components_expected_Toffolis'],
                first_loader_peak=48, second_loader_peak=48,
                quantized_exact_minimum_margin_units64=124372027,
                quantize50_sha256=digest)


def local_module(name):
    if name not in MODULES:
        path = HERE / (name + '.py')
        if name in sys.modules:
            module = sys.modules[name]
            assert Path(module.__file__).resolve() == path.resolve()
        else:
            spec = importlib.util.spec_from_file_location('candidate06_' + name, path)
            module = importlib.util.module_from_spec(spec)
            # Local adapters may import one another by their plain file names.
            # Keep one module/class identity under both spellings.
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
        local_module('divider_cleanup06').install(divider)
        local_module('phase06').install(previous)
        _INSTALLED = True
    return divider


def load_baseline(name):
    return previous.load_baseline(name)


def proof50_module():
    # The immutable candidate04 proof imports this entry-point module as
    # `variant`; its unchanged mathematical oracle uses only the pinned angles.
    return previous.proof50_module()
