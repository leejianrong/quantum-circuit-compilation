#!/usr/bin/env python3
# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Emit a candidate10-derived variant without editing any pinned source file.

Usage (through tools/macrun.py on macOS):
    macrun.py tools/build_variant.py --out DIR [--patch PATCH.py] [--postpass REWRITES.json] [--name NAME]

The build is candidate10's generate.build() step for step. A PATCH module may define
    Q = 48                                   # declared peak width (builder.set_max_qubits)
    def apply(ctx): ...                      # monkeypatch loaded modules before emission
ctx has: variant (candidate10 arithmetic_variant), old (candidate07 variant), components
(dict: normalization, root, divider, product, coefficient, lifecycle), baseline
(lifecycle06 baseline), tables, decoder, phase, common, km.
A patch replaces attributes on those live module objects (e.g. components['root'] =
my_module, or ctx.baseline.seed_forward = my_function). Pinned files on disk stay
byte-identical, so every hash check in the frozen sources still runs and passes.

--postpass applies kmx-level rewrite records (tools/postpass.py) to the emitted text.

Nothing here asserts an expected Toffoli count: the actual exact expectation of the
emitted text is computed and reported. A variant counts only after tools/prove_any.py
(unchanged exact50 checker and oracle, full domain, every HMR transcript) and the
official verifier on salts default/1/2/3.
"""
from pathlib import Path
import argparse, hashlib, importlib.util, json, sys, time

HERE = Path(__file__).resolve().parent
FG = HERE.parent
NARROW = FG / 'work/c10/narrow'
CAND10 = NARROW / 'arithmetic_round2/native/candidate10'
sys.path.insert(0, str(CAND10))
sys.path.insert(0, str(HERE))


def load_patch(path):
    if path is None:
        return None
    spec = importlib.util.spec_from_file_location('variant_patch_' + Path(path).stem, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class Context:
    pass


class PatchSet:
    """Several patch modules applied in order; later ones win on Q and emit_body."""

    def __init__(self, modules):
        self.modules = [m for m in modules if m is not None]
        for m in self.modules:
            if hasattr(m, 'Q'):
                self.Q = m.Q
            if hasattr(m, 'emit_body'):
                self.emit_body = m.emit_body

    def apply(self, ctx):
        for m in self.modules:
            if hasattr(m, 'apply'):
                m.apply(ctx)


def build(patch=None, Q=None):
    import arithmetic_variant as variant
    from branch_prover import Program, generated_text
    from fourier_resource_expectation import exact_expectation
    gate = variant.accepted_gate()
    components = dict(variant.install())
    old = variant.old
    common = old.common
    base = old.load_baseline('generate')
    ctx = Context()
    ctx.variant, ctx.old, ctx.components, ctx.common, ctx.km = variant, old, components, common, common.km
    ctx.baseline = components['lifecycle'].baseline
    ctx.tables = old.local_module('tables07')
    ctx.decoder = old.inherited_module('decoder06')
    ctx.phase = old.local_module('phase07')
    ctx.base = base
    ctx.gate = gate
    width = Q if Q is not None else getattr(patch, 'Q', gate['Q'])
    if patch is not None and hasattr(patch, 'apply'):
        patch.apply(ctx)
    lifecycle = ctx.components['lifecycle']
    builder = common.km.CircuitBuilder()
    builder.set_max_qubits(width)
    original = list(builder.alloc_qubits(22))
    flags = list(builder.alloc_qubits(4))
    cuts, owner_trace = [], []

    def mark(label, current, owners):
        cuts.append(base.snapshot(current, label, owners))

    lifecycle.CUT_HOOK = mark
    ctx.components['normalization'].forward(builder, original, flags)
    mark('normalized', builder, dict(n=original, flags=flags))
    root = ctx.components['root'].forward(builder, original)
    v, h = list(root['root']), list(root['residual'])
    mark('consumed_root', builder, dict(v=v, h=h, flags=flags))
    emit_body = getattr(patch, 'emit_body', None) or lifecycle.emit_body
    v, h = emit_body(builder, v, h, flags, ctx.tables, old.divider, ctx.decoder.decode_root, trace=owner_trace)
    assert len(set(v + h + flags)) == 26 and builder.num_allocated_qubits == 26
    mark('body_restored', builder, dict(v=v, h=h, flags=flags))
    norm = h + v
    ctx.components['root'].inverse(builder, norm)
    mark('root_restored', builder, dict(n=norm, flags=flags))
    ctx.components['normalization'].inverse(builder, norm, flags)
    builder.free(common.array(flags))
    mark('logical_input_restored', builder, dict(x=norm))
    layout = base.restore_input_layout(builder, norm, original, width)
    circuit = common.with_registers(builder.finish_circuit(), dict(x=original))
    text = generated_text(circuit)
    variant.verify_sources()
    return ctx, circuit, text, cuts, owner_trace, layout


def cost_model(resources, Q, margin_units64=124370688):
    import math
    mean = resources['mean_numeric']
    rotations = mean['generic_rotations']
    eps = math.pi * margin_units64 / 2**64 / rotations if rotations else None
    charge = rotations * (0.56 * math.log2(1 / eps) + 5.3) / 4 if rotations else 0.0
    per_shot = mean['toffoli_like'] + mean['T'] / 4 + charge
    return dict(Q=Q, toffoli_like=mean['toffoli_like'], T=mean['T'], generic_rotations=rotations,
                rotation_charge=charge, per_shot=per_shot, modelled_cost=Q * per_shot,
                label='modelled from exact gate expectation; margin assumed unchanged; not measured')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--patch', type=Path, action='append', default=[])
    ap.add_argument('--postpass', type=Path)
    ap.add_argument('--name', default='variant')
    ap.add_argument('--Q', type=int)
    args = ap.parse_args()
    began = time.monotonic()
    patch = PatchSet([load_patch(path) for path in args.patch]) if args.patch else None
    ctx, circuit, text, cuts, owner_trace, layout = build(patch, args.Q)
    from branch_prover import Program, generated_text
    from fourier_resource_expectation import exact_expectation
    km = ctx.km
    postpass_report = None
    if args.postpass is not None:
        import postpass
        text, postpass_report = postpass.apply_rewrites(text, json.loads(args.postpass.read_text()))
        circuit = km.Circuit(text)
        text = generated_text(circuit)
    program, resources = Program(text), exact_expectation(text)
    assert list(circuit.register_data) == ['x'] and len(circuit.register_data['x']) == 22
    assert program.modulus == 1 << 50, program.modulus
    args.out.mkdir(parents=True, exist_ok=True)
    kmb = args.out / (args.name + '.kmb')
    circuit.to_file(str(kmb), format='kmb')
    kmb.with_suffix('.kmx').write_text(text)
    model = cost_model(resources, circuit.num_qubits)
    report = dict(status='EMITTED_VARIANT_NOT_YET_PROVED_OR_QUALIFIED', name=args.name,
                  base='candidate10 generator, unmodified pinned sources',
                  patch=[str(path) for path in args.patch],
                  patch_sha256=[hashlib.sha256(path.read_bytes()).hexdigest() for path in args.patch],
                  postpass=str(args.postpass) if args.postpass else None, postpass_report=postpass_report,
                  Q=circuit.num_qubits, exact_native_expectation=resources, cost_model=model,
                  cuts=cuts, owner_trace=owner_trace, final_Clifford_layout_swaps=layout,
                  actual_HMR_variables=program.measurements, native_operations=len(program.operations),
                  kmb_sha256=hashlib.sha256(kmb.read_bytes()).hexdigest(),
                  native_text_sha256=hashlib.sha256(text.encode()).hexdigest(),
                  emission_seconds=time.monotonic() - began, official_verifier=False, no_submission=True)
    kmb.with_suffix('.build.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(name=args.name, kmb=str(kmb), kmb_sha256=report['kmb_sha256'], cost_model=model,
                          static=resources['static'], HMR=program.measurements,
                          seconds=report['emission_seconds']), indent=1), flush=True)


if __name__ == '__main__':
    main()
