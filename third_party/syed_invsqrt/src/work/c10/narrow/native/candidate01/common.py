# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0
# Credits: Opus and Astra.
"""Pinned own-source runtime for the first Q49 narrow native candidate."""
from pathlib import Path
import os,sys,json,hashlib
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
HERE=Path(__file__).resolve().parent
NARROW=HERE.parents[1]
ENGINE=NARROW/'checkpoint002/cleanroom/baseline_stage97/engine'
TESTS=NARROW/'checkpoint002/cleanroom/baseline_stage97/tests'
TOOLING=NARROW/'checkpoint002/cleanroom/baseline_stage97/tooling'
KICKMIX=NARROW/'base/official/kickmix'
sys.path[:0]=[str(KICKMIX),str(ENGINE),str(TESTS),str(TOOLING),str(NARROW/'checkpoint002/cleanroom/odd_sqrt')]
assert hashlib.sha256((KICKMIX/'kickmix.so').read_bytes()).hexdigest()=='c66b3216c4029e0cdfd09054306aa0feadf53ab2f50c1164e37f752874e5005e'
assert hashlib.sha256((ENGINE/'codebook.py').read_bytes()).hexdigest()=='9c6073d78becea467d37805131fdcc572e530c72acef5664b08057ef883f17be'
import kickmix as km
import codebook as cb
MODEL_PATH=NARROW/'research/recompute_root/models/phasefit_z1_K7_G4_m37_virtual_quadS2_36_12c0.json'
MODEL_SHA='24fff823faa911afe93d02afc3ded0bbd156a210a85f1265c989a087f8fd1219'
assert hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest()==MODEL_SHA
MODEL=json.loads(MODEL_PATH.read_text())


def checked_json(path,sha):
    path=Path(path);raw=path.read_bytes();actual=hashlib.sha256(raw).hexdigest()
    assert actual==sha,(str(path),actual,sha)
    return json.loads(raw)


def plan_from_json(p):
    return cb.QuadraticCodePlan(p['width'],p['constant'],p['linear'],
        tuple(tuple(x)for x in p['edges']),tuple(tuple(x)for x in p['products']),p['product_linear'])


def array(wires):return km.array(list(wires))


def with_registers(circuit,registers):
    """Declare input metadata without making reusable builder owners permanent.

Kickmix's create_quantum_register reserves permanent builder-owned wires,
which cannot be freed during an in-place consuming computation. Allocate
input wires normally and attach their ORIGINAL physical register identities
to the emitted own circuit. Metadata adds no gates and no new qubits.
"""
    from branch_prover import generated_text
    assert circuit.num_registers==0,'Register metadata was already attached.'
    declarations=[];all_wires=[]
    for index,(name,wires)in enumerate(registers.items()):
        wires=list(wires);assert all(isinstance(q,km.q)for q in wires)
        all_wires.extend(wires)
        declarations.extend(f'APPEND_TO_REGISTER {q} r{index}'for q in wires)
        declarations.append(f'REGISTER r{index} {json.dumps(name)}')
    assert len(set(all_wires))==len(all_wires)
    result=km.Circuit('\n'.join(declarations)+'\n'+generated_text(circuit))
    assert result.num_qubits==circuit.num_qubits
    assert list(result.register_data)==list(registers)
    for name,wires in registers.items():assert list(result.register_data[name])==list(wires)
    return result


def current_gate():
    return checked_json(NARROW/'research/lifecycle_schedule/post008_gate_v4.json',
        '0e49c0e309c3a816d9e0512d5d815de44a1fc5a1de3b5eff866330c6017954b3')


def verify_gate_sources():
    gate=current_gate()
    for path,digest in gate['source_pins'].items():
        assert hashlib.sha256((NARROW/path).read_bytes()).hexdigest()==digest,path
    return gate
