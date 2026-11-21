# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Hash-bound arithmetic adapters; protected phase and loader sources intact."""
from pathlib import Path
import hashlib, importlib.util, json, os, sys

for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[name] = '1'

HERE = Path(__file__).resolve().parent
NARROW = HERE.parents[2]
ROUND = NARROW / 'arithmetic_round2'
BASE = NARROW / 'native/candidate07'
# Filled from the complete reviewed gate before SOURCE_READY is frozen.
GATE_SHA = 'eb427769c7166ea94422a4d910cd47a2284c38f46f4eb311885ed6b86e6eb714'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_manifest(path, root):
    manifest = json.loads(Path(path).read_text())
    for pin in manifest['files']:
        source = root / pin['path']
        raw = source.read_bytes()
        assert len(raw) == pin['bytes'], pin['path']
        assert hashlib.sha256(raw).hexdigest() == pin['sha256'], pin['path']
    return manifest


def verify_sources():
    check_manifest(HERE / 'INPUTS.json', NARROW)
    check_manifest(HERE / 'SOURCE_READY.json', HERE)
    assert sha(BASE / 'SOURCE_READY.json') == 'f83afb14d599c704b32118abe75d0a4cbf2a71b85aa96f76fa24a9877477ab06'
    check_manifest(BASE / 'SOURCE_READY.json', BASE)
    protected = json.loads((ROUND / 'PROTECTED_INTERFACES.json').read_text())
    for pin in protected['files']:
        assert sha(NARROW / pin['path']) == pin['sha256'], pin['path']


def load(name, path):
    path = Path(path).resolve()
    pins = json.loads((HERE / 'INPUTS.json').read_text())['files']
    selected = [pin for pin in pins if (NARROW / pin['path']).resolve() == path]
    assert len(selected) == 1 and sha(path) == selected[0]['sha256'], str(path)
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    module = sys.modules[name]
    assert Path(module.__file__).resolve() == path
    return module


verify_sources()
# The immutable loader imports this exact canonical module identity.
old = load('variant', BASE / 'variant.py')
_INSTALLED = None


def accepted_gate():
    verify_sources()
    assert sha(HERE / 'COMPLETE_GATE.json') == GATE_SHA
    gate = json.loads((HERE / 'COMPLETE_GATE.json').read_text())
    accepted = json.loads((HERE / 'PARENT_ACCEPTED.json').read_text())
    assert accepted['native_build_authorized']
    assert accepted['complete_gate_sha256'] == GATE_SHA
    assert accepted['all_selected_components_native_proved']
    assert gate['Q'] == 48 and gate['expected_Toffolis'] == 1548.75
    assert gate['T'] == 4 and gate['R'] == 33
    assert sum(gate['components_expected_Toffolis'].values()) == gate['expected_Toffolis']
    assert gate['first_preparation_peak'] == gate['second_preparation_peak'] == gate['endpoint_peak'] == 48
    assert gate['rotation_charge'] == 230.84805946161188
    assert gate['expected_cost'] == 48 * (1548.75 + 1 + gate['rotation_charge'])
    assert gate['original_exact_minimum_margin_units64'] == 124370688
    assert gate['independent_phase_units50_sha256'] == '8bd482a8957cd387a2b212afdaca656947b7f89c983d67ff4eea4e14c3b0a26a'
    assert gate['original_tolerance_unchanged'] and gate['protected_phase_tables_angles_oracle_unchanged']
    fit, digest = old.accuracy_receipt()
    assert digest == gate['accuracy_receipt_sha256']
    assert fit['exact_screen']['phase50_sha256'] == gate['independent_phase_units50_sha256']
    return gate


def install():
    global _INSTALLED
    gate = accepted_gate()
    if _INSTALLED is None:
        old.install()
        modules = {name: load('candidate10_adapter_' + name, NARROW / path)
                   for name, path in gate['adapter_paths'].items()}
        import lifecycle10
        assert Path(lifecycle10.__file__).resolve() == HERE / 'lifecycle10.py'
        lifecycle = lifecycle10
        baseline = old.inherited_module('lifecycle06').baseline
        lifecycle.baseline = baseline
        modules['lifecycle'] = lifecycle
        coefficient = modules['coefficient']
        product = modules['product']

        def coefficient_inverse(builder, v, D, H, token, dirty):
            return coefficient.coefficient_inverse(builder, v, D, H, token, dirty,
                                                   baseline=baseline)

        def product_inverse(builder, v, D, word, token, dirty):
            return product.product_inverse(builder, v, D, word, token, dirty,
                                            baseline=baseline)

        baseline.coefficient_inverse = coefficient_inverse
        lifecycle.product_inverse = product_inverse
        modules['divider'].install(old.divider)
        _INSTALLED = modules
    verify_sources()
    return _INSTALLED
