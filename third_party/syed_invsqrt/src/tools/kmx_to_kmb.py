#!/usr/bin/env python3
# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Compile a kmx text to the canonical .kmb/.kmx pair and report its exact expected resources.

    macrun.py tools/kmx_to_kmb.py IN.kmx --out DIR/NAME.kmb [--provenance FILE.json ...]

Writes NAME.kmb, NAME.kmx (kickmix's own serialisation) and NAME.build.json with the exact
guard-weighted expectation and the modelled cost. Nothing is proved or verified here.
"""
from pathlib import Path
import argparse, hashlib, json, sys, time

HERE = Path(__file__).resolve().parent
FG = HERE.parent
CAND10 = FG / 'work/c10/narrow/arithmetic_round2/native/candidate10'
sys.path.insert(0, str(CAND10))
sys.path.insert(0, str(HERE))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('kmx', type=Path)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--provenance', type=Path, action='append', default=[])
    args = ap.parse_args()
    began = time.monotonic()
    import arithmetic_variant as variant
    from branch_prover import Program, generated_text
    from fourier_resource_expectation import exact_expectation
    from build_variant import cost_model
    km = variant.old.common.km
    circuit = km.Circuit(args.kmx.read_text())
    text = generated_text(circuit)
    program, resources = Program(text), exact_expectation(text)
    assert list(circuit.register_data) == ['x'] and len(circuit.register_data['x']) == 22
    assert program.modulus == 1 << 50
    args.out.parent.mkdir(parents=True, exist_ok=True)
    circuit.to_file(str(args.out), format='kmb')
    args.out.with_suffix('.kmx').write_text(text)
    report = dict(status='COMPILED_FROM_TEXT_NOT_YET_PROVED_OR_QUALIFIED', source_kmx=str(args.kmx),
                  source_kmx_sha256=hashlib.sha256(args.kmx.read_bytes()).hexdigest(),
                  provenance={str(p): json.loads(p.read_text()) for p in args.provenance},
                  Q=circuit.num_qubits, exact_native_expectation=resources,
                  cost_model=cost_model(resources, circuit.num_qubits),
                  actual_HMR_variables=program.measurements, native_operations=len(program.operations),
                  kmb_sha256=hashlib.sha256(args.out.read_bytes()).hexdigest(),
                  native_text_sha256=hashlib.sha256(text.encode()).hexdigest(),
                  seconds=time.monotonic() - began, official_verifier=False, no_submission=True)
    args.out.with_suffix('.build.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(kmb=str(args.out), kmb_sha256=report['kmb_sha256'], cost_model=report['cost_model'],
                          static=resources['static'], HMR=program.measurements), indent=1), flush=True)


if __name__ == '__main__':
    main()
