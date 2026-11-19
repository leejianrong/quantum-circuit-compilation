#!/usr/bin/env python3
# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Full-domain exact native proof of ANY invsqrt circuit against the frozen phase oracle.

Calls the unchanged candidate07 exact50 proof functions (pinned checker
whole_text_symbolic.py, pinned ring26 oracle50.py, 5 positive + 9 negative
self-tests) exactly as candidate10's prove50.py does, but takes the expected
resources from the circuit itself instead of a frozen paper gate:

    macrun.py tools/prove_any.py --circuit X.kmb --out X.proof.json [--mode text|sample|selftest]

Text mode proves every x in [1, 3133453), every HMR transcript, exact phase equal to
the frozen integer model, original input restored, scratch zero, resets on zero.
It also re-derives the full-domain phase digest and requires the frozen value.
"""
from pathlib import Path
import argparse, hashlib, importlib.util, json, resource, sys, time

HERE = Path(__file__).resolve().parent
FG = HERE.parent
NARROW = FG / 'work/c10/narrow'
CAND10 = NARROW / 'arithmetic_round2/native/candidate10'
sys.path.insert(0, str(CAND10))


def original_proof(variant):
    path = variant.NARROW / 'native/candidate07/prove50.py'
    assert variant.sha(path) == 'd079cefb01fa88581cf279e99590ad74610551861658f5fef65ff9071650216e'
    name = 'immutable_candidate07_proof50'
    if name not in sys.modules:
        previous = sys.modules.get('variant')
        sys.modules['variant'] = variant.old
        try:
            spec = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
        finally:
            if previous is None:
                sys.modules.pop('variant', None)
            else:
                sys.modules['variant'] = previous
    proof = sys.modules[name]
    assert proof.variant is variant.old and proof.MODULUS == 1 << 50 and proof.MAX_X == 3133452
    return proof


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--circuit', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--mode', choices=('selftest', 'sample', 'text'), default='text')
    args = ap.parse_args()
    began = time.monotonic()
    import arithmetic_variant as variant
    from branch_prover import Program, generated_text
    from fourier_resource_expectation import exact_expectation
    proof = original_proof(variant)
    fit, fit_sha = variant.old.accuracy_receipt()
    assert fit_sha == 'c0eab1edd234e32d5baa1a51a0fec46abf82165d3973ffda825d2149f67f11e5'
    assert fit['exact_screen']['phase50_sha256'] == '8bd482a8957cd387a2b212afdaca656947b7f89c983d67ff4eea4e14c3b0a26a'
    tests = proof.selftest50()
    assert tests['positive_cases'] == 5 and tests['negative_cases'] == 9
    if args.mode == 'selftest':
        result = tests
    else:
        digest = variant.sha(args.circuit)
        circuit = variant.old.common.km.Circuit.from_file(str(args.circuit))
        assert list(circuit.register_data) == ['x'] and len(circuit.register_data['x']) == 22
        text = generated_text(circuit)
        assert Program(text).modulus == 1 << 50
        resources = exact_expectation(text)
        if args.mode == 'sample':
            result = proof.native_sample(circuit, 8192, [0, 1, 2, 3])
            result['status'] = 'PASS_NATIVE_SAMPLED_NOT_OFFICIAL'
        else:
            scratch_out = args.out.with_suffix('.work.json')
            result = proof.exhaustive_text(circuit, 1, proof.MAX_X + 1, 65536, scratch_out, fit)
            assert result['whole_official_domain'] and result['proved_inputs'] == proof.MAX_X
            assert result['phase_units50_sha256'] == fit['exact_screen']['phase50_sha256']
        result.update(circuit_sha256=digest, Q=circuit.num_qubits, exact50_unit_selftest=tests,
                      exact_native_expectation=resources)
    variant.verify_sources()
    result.update(phase_basis='ring26_global_zero33', phase_modulus=1 << 50,
                  accuracy_receipt_sha256=fit_sha, quantized_exact_minimum_margin_units64=124370688,
                  unchanged_original_tolerance=True, protected_phase_oracle_unchanged=True,
                  original_candidate07_proof_source_sha256=variant.sha(variant.NARROW / 'native/candidate07/prove50.py'),
                  original_oracle_source_sha256=variant.sha(variant.NARROW / 'native/candidate07/oracle50.py'),
                  driver_source_sha256=variant.sha(Path(__file__)),
                  official_verifier=False, no_submission=True, elapsed_seconds=time.monotonic() - began,
                  peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    proof.atomic(args.out, result)
    print(json.dumps({k: v for k, v in result.items() if k not in ('chunks', 'exact50_unit_selftest')},
                     indent=1, default=str), flush=True)


if __name__ == '__main__':
    main()
