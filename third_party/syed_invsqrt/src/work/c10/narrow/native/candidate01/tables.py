# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0
# Credits: Opus and Astra.
"""Pinned own joint A/H loaders and exact deferred table-phase cleanup.

The first/second loaders use60/73 unconditional CCX gates and return the same
sixteen physical output meanings. All helper measurement phases are explicitly
owned by TableDebts until the original raw address and A/H chart is restored.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
from typing import Any

from common import km,cb,NARROW,MODEL,MODEL_SHA,checked_json,plan_from_json,array

FROZEN=NARROW/'research/joint_loader/frozen'
PINS={
    'first':('loader16_first60.json','3bcbd49ad53c0e2661bbc1112d172c854d4bf50ba4ea1f9a119a077f8e6cd9fd'),
    'second':('loader16_second73.json','52db753c9efef945c9194ed4a39ec3b250221b69eb10e0030dc2a283f659eafc'),
    'cleanup':('retained_table_cleanup9.json','6a48b472433918d2c51f30e6eeb1d9933fdf1aa4ae9f83b93129fd8ac103b6b5'),
}
CODEBOOK_SHA='9c6073d78becea467d37805131fdcc572e530c72acef5664b08057ef883f17be'
assert hashlib.sha256((NARROW/'checkpoint002/cleanroom/baseline_stage97/engine/codebook.py').read_bytes()).hexdigest()==CODEBOOK_SHA
assert hashlib.sha256((NARROW/'base/official/kickmix/kickmix.so').read_bytes()).hexdigest()=='c66b3216c4029e0cdfd09054306aa0feadf53ab2f50c1164e37f752874e5005e'
FULL=(1<<128)-1


@dataclass(frozen=True)
class TableDebt:
    outcome: Any
    truth128: int


class TableDebts:
    """Own all recorded measurement bits until exact Clifford repayment.

Only unconditional HMR of a certified function of the original raw seven-bit
table address belongs here. Surrounding classical conditions would require a
separate guard-aware extension; they must not be omitted from a debt.
"""
    def __init__(self):
        self.pending=[]
        self._owned=set()
        self.total_recorded=0

    def record(self,outcome,truth128):
        truth128=int(truth128)
        if not isinstance(outcome,km.b):raise TypeError('A table HMR outcome must be a classical bit.')
        if outcome in self._owned:raise ValueError('A table HMR outcome already has an owner.')
        if not 0<=truth128<=FULL:raise ValueError('A seven-bit table truth must contain at most128 rows.')
        self.pending.append(TableDebt(outcome,truth128));self._owned.add(outcome);self.total_recorded+=1

    def erase(self,builder,wire,truth128,*,free=False):
        outcome=builder.alloc_bits(1)[0]
        builder.hmr(wire,outcome);self.record(outcome,truth128)
        if free:builder.free(wire)
        return outcome

    def flush(self,builder,variables,functions):
        """Pay every complete debt using a certified current quadratic chart."""
        variables=list(variables);functions=list(map(int,functions))
        if len(variables)!=len(functions):raise ValueError('Phase variables and truth coordinates differ.')
        book=cb.Codebook(functions,128)
        if len(book.span.pivots)!=128:raise ValueError('The supplied table phase chart is not universal.')
        count=len(self.pending)
        for debt in self.pending:
            expression=book.span.solve(debt.truth128)
            if expression is None:raise AssertionError('A pending table truth is outside the live phase chart.')
            plan=book.decode_expression(expression)
            assert plan.evaluate_functions(functions,FULL)==debt.truth128
            cb.emit_phase(builder,variables,debt.outcome,plan)
            builder.free(debt.outcome)
        self.pending.clear();self._owned.clear()
        return dict(outcomes=count,Toffolis=0,quadratic_rank=128)


@lru_cache(maxsize=3)
def certificate(which):
    name,digest=PINS[which]
    data=checked_json(FROZEN/name,digest)
    assert data['model_sha256']==MODEL_SHA
    return data


@lru_cache(maxsize=1)
def model_values():
    return dict(A=tuple(map(int,MODEL['A'])),S=tuple(map(int,MODEL['S'])),
                H=tuple(map(int,MODEL['stored_slope'])))


@lru_cache(maxsize=1)
def model_truths():
    values=model_values()
    return dict(address=tuple(cb.word_functions(range(128),7)),
                A=tuple(cb.word_functions(values['A'],13)),
                S=tuple(cb.word_functions(values['S'],6)),
                H=tuple(cb.word_functions(values['H'],5)))


def _row_matrix_inverse_operations(rows,width):
    matrix=list(map(int,rows));ops=[]
    if len(matrix)!=width or any(row>>width for row in matrix):raise ValueError('Wrong Clifford matrix shape.')
    for column in range(width):
        pivot=next((r for r in range(column,width) if matrix[r]>>column&1),None)
        if pivot is None:raise ValueError('A requested physical Clifford frame is singular.')
        if pivot!=column:
            matrix[pivot],matrix[column]=matrix[column],matrix[pivot];ops.append(('swap',pivot,column))
        for row in range(width):
            if row!=column and matrix[row]>>column&1:
                matrix[row]^=matrix[column];ops.append(('cx',column,row))
    assert matrix==[1<<i for i in range(width)]
    return tuple(reversed(ops))


def _swap(builder,a,b):
    if a==b:return
    builder.cx(a,b);builder.cx(b,a);builder.cx(a,b)


def emit_affine_frame(builder,address,work,rows):
    """Apply an invertible work-wire matrix plus raw-address affine terms."""
    address=list(address);work=list(work);rows=list(map(int,rows))
    if len(address)!=7:raise ValueError('Expected seven unchanged raw address wires.')
    for kind,a,b in _row_matrix_inverse_operations([row>>8 for row in rows],len(work)):
        if kind=='cx':builder.cx(work[a],work[b])
        else:_swap(builder,work[a],work[b])
    for target,row in zip(work,rows):
        if row&1:builder.x(target)
        for bit in range(7):
            if row>>(1+bit)&1:builder.cx(address[bit],target)


def _affine_xor(builder,address,previous,target,expression):
    if expression&1:builder.x(target)
    variables=list(address)+list(previous)
    for bit in cb.bits(expression>>1):builder.cx(variables[bit],target)


def load_joint16(builder,address7,*,variant,debts):
    """Allocate, load and return(A13,Hlow3), preserving raw address7.

    The complete reusable work pool is23/18 qubits, including all16 outputs.
    Seven/two zero helpers are released on return. Quantum input owners outside
    this function are26/31 respectively in the complete Q49 circuit.
    """
    if variant not in ('first','second'):raise ValueError('variant must be first or second.')
    address=list(address7)
    if len(address)!=7 or len(set(address))!=7:raise ValueError('Expected seven distinct raw address wires.')
    if not isinstance(debts,TableDebts):raise TypeError('Expected the shared TableDebts owner.')
    data=certificate(variant);cap=data['work_cap'];pool=list(builder.alloc_qubits(cap));available=list(pool);work=[]
    actual_count=0
    for item in data['steps']:
        kind=item['kind']
        if kind=='bank':
            target=available.pop(0);plan=plan_from_json(item['plan'])
            cb.emit_xor(builder,address+work,target,plan);work.append(target);actual_count+=plan.and_count
        elif kind=='Clifford_zero_dependent_coordinate':
            index=item['index'];target=work[index]
            _affine_xor(builder,address,work[:index],target,item['expression'])
            work.pop(index);available.append(target)
        elif kind=='Clifford_frame_then_HMR':
            emit_affine_frame(builder,address,work,item['full_affine_rows'])
            kept=item['retained_count'];discard=work[kept:]
            assert len(discard)==len(item['discarded_truths'])
            for wire,truth in zip(discard,item['discarded_truths']):
                debts.erase(builder,wire,int(truth,16));available.append(wire)
            work=work[:kept]
        elif kind=='virtual_affine_product':
            pass
        elif kind=='CCX_new_coordinate':
            target=available.pop(0);plan=plan_from_json(item['plan'])
            cb.emit_xor(builder,address+work,target,plan);work.append(target);actual_count+=plan.and_count
        elif kind=='XOR_product_existing_coordinate':
            assert item['target_index']==0
            plan=plan_from_json(item['plan']);cb.emit_xor(builder,address+work[1:],work[0],plan);actual_count+=plan.and_count
        elif kind=='final_output_Clifford_frame':
            emit_affine_frame(builder,address,work,[int(row)<<8 for row in item['matrix_rows']])
        else:raise AssertionError(f'Unknown frozen loader operation:{kind}')
        assert len(work)+len(available)==cap and len(set(work+available))==cap
    assert len(work)==16 and actual_count==data['Toffolis']==(60 if variant=='first' else 73)
    if available:builder.free(array(available))
    return list(work[:13]),list(work[13:16])


def cleanup_joint16(builder,address7,A13,Hlow3,debts):
    """Repay all table debts and erase/free the sixteen outputs for9CCX."""
    address=list(address7);A=list(A13);H=list(Hlow3)
    if (len(address),len(A),len(H))!=(7,13,3):raise ValueError('Wrong final table chart widths.')
    if len(set(address+A+H))!=23:raise ValueError('Final table chart owners overlap.')
    truths=model_truths();outputs=A+H;functions=list(truths['address'])+list(truths['A'])+list(truths['H'][:3])
    flushed=debts.flush(builder,address+outputs,functions)
    data=certificate('cleanup');case=next(c for c in data['cases'] if c['output_count']==16)
    emit_affine_frame(builder,address,outputs,[int(row)<<8 for row in case['output_Clifford_basis_rows']])
    wires={f'r{i}':wire for i,wire in enumerate(address)}
    wires.update({f'c{i}':wire for i,wire in enumerate(outputs)})
    count=0
    for item in case['steps']:
        kind=item['kind']
        if kind=='bank':
            variables=[wires[name] for name in item['inputs']];target=builder.alloc_qubits(1)[0]
            plan=plan_from_json(item['plan']);cb.emit_xor(builder,variables,target,plan)
            wires[item['name']]=target;count+=plan.and_count
        elif kind in ('HMR_output','HMR_bank'):
            variables=[wires[name] for name in item['retained']];target=wires.pop(item['name'])
            plan=plan_from_json(item['phase_plan']);cb.emit_erase(builder,variables,[target],[plan]);builder.free(target)
        else:raise AssertionError(f'Unknown cleanup operation:{kind}')
    assert count==9 and set(wires)=={f'r{i}' for i in range(7)} and not debts.pending
    return dict(Toffolis=9,table_debts_repaid=flushed['outcomes'],quantum_outputs_erased=16)
