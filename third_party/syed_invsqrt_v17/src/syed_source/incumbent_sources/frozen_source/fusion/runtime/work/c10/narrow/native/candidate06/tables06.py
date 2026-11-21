# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0
# Credits: Opus and Astra.
"""Isolated Q48 first61/framed-second80 coefficient table adapters.

The second loader consumes four existing address owners as mutable work.
Every discarded value retains its exact original-raw-address phase function.
The caller must mark those four logical root slots absent immediately.
"""
from pathlib import Path
from functools import lru_cache
import hashlib
import importlib.util
import sys
from common import km, cb, NARROW, MODEL_SHA, checked_json, plan_from_json, array

HERE=Path(__file__).resolve().parent
BASE_PATH=HERE.parent/'candidate01/tables.py'
BASE_SHA='cf2c83b6db5d1b1e2a63f4fe6e84976192a49eabb74e370ee2376fc4300659d3'
assert hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()==BASE_SHA
_spec=importlib.util.spec_from_file_location('_candidate06_pinned_tables01',BASE_PATH)
_BASE=importlib.util.module_from_spec(_spec)
sys.modules[_spec.name]=_BASE
_spec.loader.exec_module(_BASE)

TableDebt=_BASE.TableDebt
TableDebts=_BASE.TableDebts
model_values=_BASE.model_values
model_truths=_BASE.model_truths
cleanup_joint16=_BASE.cleanup_joint16

FROZEN=NARROW/'research/joint_loader/frozen'
PINS={
    'first':('loader16_first61_Q48.json','4857688e595af50828d7bedf0bc745eaaed8d10767e2e6ca6f77802887e1ad48'),
    'second':('loader16_second80_framed_Q48.json','e4f007d322caae5c77b3d61c61d73fb239126e67a488238ece442b1f51d8a805'),
}
SECOND_RETIRED_ADDRESS_SLOTS=(0,1,2,4)
RESOURCES={
    'first':dict(Toffolis=61,T=0,R=0,other_fixed_owners=26,work_cap=22,
                 existing_input_work=0,new_zero_owners=22,complete_peak=48,return_owners=42,HMR_debts=45),
    'second':dict(Toffolis=80,T=0,R=0,other_fixed_owners=27,work_cap=21,
                  existing_input_work=4,new_zero_owners=17,complete_peak=48,return_owners=43,HMR_debts=64),
    'cleanup':dict(Toffolis=9,T=0,R=0,complete_peak=44),
}


@lru_cache(maxsize=2)
def certificate(which):
    name,digest=PINS[which]
    data=checked_json(FROZEN/name,digest)
    assert data['model_sha256']==MODEL_SHA
    assert data['status']=='COMPLETE_MATHEMATICAL_LOADER_NOT_NATIVE'
    assert data['Toffolis']==RESOURCES[which]['Toffolis']
    assert data['work_cap']==data['work_peak']==RESOURCES[which]['work_cap']
    assert data['complete_peak']==48
    return data


def emit_affine_frame(builder,fixed,work,rows):
    """Invertible work frame with offset8(raw7) or4(fixed R,a5,a6)."""
    fixed=list(fixed);work=list(work);rows=list(map(int,rows))
    if len(fixed)not in(3,7):raise ValueError('Unexpected fixed-address chart width.')
    offset=1+len(fixed)
    for kind,a,b in _BASE._row_matrix_inverse_operations([row>>offset for row in rows],len(work)):
        if kind=='cx':builder.cx(work[a],work[b])
        else:_BASE._swap(builder,work[a],work[b])
    for target,row in zip(work,rows):
        if row&1:builder.x(target)
        for bit in range(len(fixed)):
            if row>>(1+bit)&1:builder.cx(fixed[bit],target)


def load_joint16(builder,address7,*,variant,debts):
    """Return current(A13,Hlow3); the second address is ALREADY R-framed.

    First: preserve raw address7, allocate22 zero owners, return16 outputs.
    Second: keep slots3,5,6=(R,rawa5,rawa6); reuse slots0,1,2,4 in workcap21
    and allocate only17 zeros. Those four old logical inputs are consumed:
    the caller sets v[5],v[6],v[7],v[9] to None before using v again.
    The shared TableDebts ledger owns all mixed/input/helper HMR outcomes.
    """
    if variant not in('first','second'):raise ValueError('Unknown Q48 loader variant.')
    address=list(address7)
    if len(address)!=7 or len(set(address))!=7 or not all(isinstance(q,km.q)for q in address):
        raise ValueError('Expected seven current, distinct quantum address owners.')
    if not isinstance(debts,TableDebts):raise TypeError('Expected the shared pinned TableDebts owner.')
    data=certificate(variant);entry=builder.num_allocated_qubits
    before_debts=debts.total_recorded
    fixed_slots=(0,1,2,3,4,5,6)if variant=='first'else(3,5,6)
    reusable_slots=()if variant=='first'else SECOND_RETIRED_ADDRESS_SLOTS
    assert data['fixed_address_slots']==list(fixed_slots)
    assert data['reusable_input_slots']==list(reusable_slots)
    fixed=[address[i]for i in fixed_slots]
    work=[address[i]for i in reusable_slots]
    cap=data['work_cap'];available=list(builder.alloc_qubits(cap-len(work)))
    assert len(available)==RESOURCES[variant]['new_zero_owners']
    offset=1+len(fixed);count=0
    for item in data['steps']:
        kind=item['kind']
        if kind in('bank','CCX_new_coordinate'):
            target=available.pop(0);plan=plan_from_json(item['plan'])
            cb.emit_xor(builder,fixed+work,target,plan)
            work.append(target);count+=plan.and_count
        elif kind=='Clifford_zero_dependent_coordinate':
            index=item['index'];target=work[index]
            _BASE._affine_xor(builder,fixed,work[:index],target,item['expression'])
            work.pop(index);available.append(target)
        elif kind=='Clifford_frame_then_HMR':
            assert item['affine_fixed_offset']==offset
            emit_affine_frame(builder,fixed,work,item['full_affine_rows'])
            kept=item['retained_count'];discard=work[kept:]
            assert len(discard)==len(item['discarded_truths'])
            for wire,truth in zip(discard,item['discarded_truths']):
                debts.erase(builder,wire,int(truth,16));available.append(wire)
            work=work[:kept]
        elif kind=='virtual_affine_product':
            pass
        elif kind=='XOR_product_existing_coordinate':
            assert item['target_index']==0
            plan=plan_from_json(item['plan'])
            cb.emit_xor(builder,fixed+work[1:],work[0],plan);count+=plan.and_count
        elif kind=='final_output_Clifford_frame':
            emit_affine_frame(builder,fixed,work,[int(row)<<offset for row in item['matrix_rows']])
        else:raise AssertionError(('Unknown frozen Q48 loader operation',kind))
        assert len(work)+len(available)==cap and len(set(work+available))==cap
        assert not set(fixed)&set(work+available)
    assert len(work)==16 and count==RESOURCES[variant]['Toffolis']
    assert debts.total_recorded-before_debts==RESOURCES[variant]['HMR_debts']
    if available:builder.free(array(available))
    assert builder.num_allocated_qubits==entry+16-len(reusable_slots)
    return list(work[:13]),list(work[13:])
