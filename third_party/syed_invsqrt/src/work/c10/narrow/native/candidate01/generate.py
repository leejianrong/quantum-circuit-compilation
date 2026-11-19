#!/usr/bin/env python3
# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0
# Credits: Opus and Astra.
"""Emit the complete own Q49 candidate after its frozen paper gate.

Run under the serial resource guard. Emission and exact instruction accounting
do not by themselves qualify a circuit; all native and official proofs remain
separate evidence files.
"""
from common import *
import argparse,time
import normalization
assert hashlib.sha256((NARROW/'checkpoint002/cleanroom/odd_sqrt/consuming_odd_sqrt.py').read_bytes()).hexdigest()=='0a60a631cb97dc39ea0e76e7ab2dc26300fd4f96218a73e0e56262c59586c144'
import consuming_odd_sqrt as consuming_root
from root_decode import decode_root
from layout import restore_input_layout
from branch_prover import generated_text,Program
from fourier_resource_expectation import exact_expectation


def snapshot(builder,name,owners):
    circuit=builder.finish_circuit();text=generated_text(circuit)
    return dict(name=name,live_qubits=builder.num_allocated_qubits,
                peak_so_far=circuit.num_qubits,
                instruction_cut=len(Program(text).operations),
                owners={k:[str(q) for q in v]for k,v in owners.items()},
                cumulative_expected=exact_expectation(text)['mean_numeric'])


def build():
    import tables,divider,lifecycle
    gate=verify_gate_sources();builder=km.CircuitBuilder();builder.set_max_qubits(49)
    original=list(builder.alloc_qubits(22));flags=list(builder.alloc_qubits(4))
    normalization.forward(builder,original,flags)
    cuts=[snapshot(builder,'normalized',dict(n=original,flags=flags))]
    root=consuming_root.forward(builder,original)
    v=list(root['root']);h=list(root['residual'])
    cuts.append(snapshot(builder,'consumed_root',dict(v=v,h=h,flags=flags)))
    v,h=lifecycle.emit_body(builder,v,h,flags,tables,divider,decode_root)
    assert len(set(v+h+flags))==26 and builder.num_allocated_qubits==26
    cuts.append(snapshot(builder,'body_restored',dict(v=v,h=h,flags=flags)))
    norm=h+v;consuming_root.inverse(builder,norm)
    cuts.append(snapshot(builder,'root_restored',dict(n=norm,flags=flags)))
    normalization.inverse(builder,norm,flags);builder.free(array(flags))
    cuts.append(snapshot(builder,'logical_input_restored',dict(x=norm)))
    layout=restore_input_layout(builder,norm,original,49)
    circuit=with_registers(builder.finish_circuit(),dict(x=original));text=generated_text(circuit);resources=exact_expectation(text)
    actual=resources['mean_numeric'];expected=gate['primary']
    assert circuit.num_qubits==49,('width_gate',circuit.num_qubits)
    assert actual['toffoli_like']==expected['Toffolis_expected'],('Toffoli_gate',actual,expected)
    assert actual['T']==expected['T'] and actual['generic_rotations']==expected['R'],('phase_gate',actual)
    assert list(circuit.register_data)==['x'] and list(circuit.register_data['x'])==original
    report=dict(status='EMITTED_NATIVE_CANDIDATE_NOT_YET_PROVED_OR_OFFICIALLY_VERIFIED',
                Q=circuit.num_qubits,exact_native_expectation=resources,
                paper_rotation_charge=expected['rotation_charge'],paper_cost=expected['paper_cost'],
                model_sha256=MODEL_SHA,gate_sha256=hashlib.sha256((NARROW/'research/lifecycle_schedule/post008_gate_v4.json').read_bytes()).hexdigest(),
                cuts=cuts,final_Clifford_layout_swaps=layout,official_verifier=False,no_submission=True)
    return circuit,text,report


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=HERE/'candidate01.kmb');args=ap.parse_args()
    started=time.monotonic();circuit,text,report=build();args.output.parent.mkdir(parents=True,exist_ok=True)
    circuit.to_file(str(args.output),format='kmb');args.output.with_suffix('.kmx').write_text(text)
    report.update(kmb_sha256=hashlib.sha256(args.output.read_bytes()).hexdigest(),bytes=args.output.stat().st_size,
                  emission_seconds=time.monotonic()-started,
                  native_sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in sorted(HERE.glob('*.py'))})
    args.output.with_suffix('.build.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':main()
