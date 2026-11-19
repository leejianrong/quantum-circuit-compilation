# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0
# Credits: Opus and Astra.
"""Root192 direct native emitter; immutable private helper modules only.

No inherited source/module is patched. forward/inverse preserve the same
norm22 owner interface and leave every exponent spectator untouched.
"""
from pathlib import Path
import hashlib,importlib.util,json,sys
HERE=Path(__file__).resolve().parent;NARROW=HERE.parents[3]
for pin in json.loads((HERE/'INPUTS.json').read_text())['files']:
    path=NARROW/pin['path'];raw=path.read_bytes()
    assert len(raw)==pin['bytes'] and hashlib.sha256(raw).hexdigest()==pin['sha256'],pin['path']
ENGINE=NARROW/'checkpoint002/cleanroom/baseline_stage97/engine'
sys.path[:0]=[str(NARROW/'base/official/kickmix'),str(ENGINE)]
import kickmix as km


def _private(name,path,expected):
    assert hashlib.sha256(path.read_bytes()).hexdigest()==expected
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module
    spec.loader.exec_module(module);return module


original=_private('_round2_rn3_immutable_odd_sqrt',
    NARROW/'checkpoint002/cleanroom/odd_sqrt/consuming_odd_sqrt.py',
    '0a60a631cb97dc39ea0e76e7ab2dc26300fd4f96218a73e0e56262c59586c144')
arithmetic=_private('fusion._round2_rn3_immutable_arithmetic',ENGINE/'fusion/arithmetic.py',
    '154621ee98dd8139eab601d5d794be881a5ebf38ebe1c542cf69b8fb97ee1453')
# Only the freshly isolated helper instance receives this private binding.
original.add=arithmetic.add
ORIGINAL_ROOT_STEP=original._root_step
ORIGINAL_FORWARD=original.forward
ORIGINAL_INVERSE=original.inverse


def arr(wires):return km.array(list(wires))


def last_step(builder,remainder,older,b,*,initial=False,inverse=False):
    """The inherited j11 zero-pair rule plus the new j12 carry alias."""
    remainder=list(remainder);older=list(older)
    j=len(remainder)-3
    if j<11:
        return ORIGINAL_ROOT_STEP(builder,remainder,older,b,initial=initial,inverse=inverse)
    assert j in (11,12) and not initial and isinstance(b,km.q)
    assert len(set(remainder+older+[b]))==len(remainder)+len(older)+1
    low=remainder[:3];high=remainder[3:]
    if hasattr(builder,'values'):
        pair=builder.full if inverse else 0
        assert builder.value(low[0])==builder.value(low[1])==pair
        if j==12:
            expected=(builder.full ^ builder.value(b) ^ builder.value(older[0])) if inverse else builder.full
            assert builder.value(high[0])==expected,('j12_first_high',inverse)
    if not inverse:builder.x(low[0]);builder.x(low[1])
    builder.cx(b,arr(high))
    if inverse:original._add_leading_one(builder,high,inverse=True)
    if j==12:
        builder.cx(b,high[0]);builder.cx(older[0],high[0])
        original.add(builder,older[1:],high[1:],carry_in=older[0],subtract=inverse)
    else:
        original.add(builder,older,high,carry_in=b,subtract=inverse)
    if not inverse:original._add_leading_one(builder,high)
    builder.cx(b,arr(high))
    if inverse:builder.x(low[0]);builder.x(low[1])


def initial_low_xor(builder,Q,low):
    """The preconversion low word is (1,1,1,1 xor Q1 xor Q2)."""
    builder.x(arr(low));builder.cx(Q[1],low[3]);builder.cx(Q[2],low[3])


def _p_frame(builder,Q):
    builder.cx(Q[2],Q[0]);builder.cx(Q[2],Q[1])


def _carry_frame(builder,Q,p):
    # Q3 becomes Q3 xor a2; p becomes c2 xor a2.
    builder.x(Q[3])
    for q in Q[:3]:builder.cx(q,Q[3])
    builder.x(p);builder.cx(Q[0],p);builder.cx(Q[2],p)


def _a2_xor(builder,Q,target):
    builder.x(target)
    for q in Q[:3]:builder.cx(q,target)


def carry_prepare(builder,Q):
    p,c=builder.alloc_qubits(2)
    _p_frame(builder,Q);builder.ccx(Q[0],Q[1],p);_p_frame(builder,Q)
    _a2_xor(builder,Q,c)
    _carry_frame(builder,Q,p);builder.ccx(Q[3],p,c);_carry_frame(builder,Q,p)
    return p,c


def carry_clear(builder,Q,p,c):
    _a2_xor(builder,Q,c)
    _carry_frame(builder,Q,p);builder.del_and(Q[3],p,c);_carry_frame(builder,Q,p)
    builder.free(c)
    _p_frame(builder,Q);builder.del_and(Q[0],Q[1],p);_p_frame(builder,Q)
    builder.free(p)


def convert_high(builder,Q,high,*,inverse=False):
    p,c=carry_prepare(builder,Q)
    builder.cx(Q[0],arr(high))
    if inverse:original._add_leading_one(builder,high,inverse=True)
    original.add(builder,Q[4:],high,carry_in=c,subtract=inverse)
    if not inverse:original._add_leading_one(builder,high)
    builder.cx(Q[0],arr(high))
    carry_clear(builder,Q,p,c)


def forward(builder,norm):
    norm=list(norm)
    assert len(norm)==22 and len(set(norm))==22
    builder.x(norm[20]);builder.cx(norm[20],norm[21])
    remainder=norm[20:22];roots=[]
    for j in range(1,13):
        pair=norm[20-2*j:22-2*j] if j<=10 else list(builder.alloc_qubits(2))
        if j==1:b=True;older=[];remainder=pair+remainder
        else:
            b=remainder[-1];builder.x(b);older=roots
            roots=[b]+roots;remainder=pair+remainder[:-1]
        last_step(builder,remainder,older,b,initial=j==1)
    b=remainder[-1];builder.x(b);Q=[b]+roots;W=remainder[:-1]
    initial_low_xor(builder,Q,W[:4]);builder.free(arr(W[:4]))
    convert_high(builder,Q,W[4:])
    assert Q==norm[10:] and W[4:]==norm[:10]
    return dict(root=Q,residual=W[4:])


def inverse(builder,norm):
    norm=list(norm);Q=norm[10:];high=norm[:10]
    convert_high(builder,Q,high,inverse=True)
    low=list(builder.alloc_qubits(4));initial_low_xor(builder,Q,low)
    W=low+high;b=Q[0];roots=Q[1:]
    builder.x(b);remainder=W+[b]
    for j in reversed(range(1,13)):
        pair=remainder[:2]
        if j==1:b=True;older=[]
        else:b=roots[0];older=roots[1:]
        last_step(builder,remainder,older,b,initial=j==1,inverse=True)
        if j==1:remainder=remainder[2:]
        else:
            remainder=remainder[2:]+[b];builder.x(b);roots=older
        if j>=11:builder.free(arr(pair))
        else:assert pair==norm[20-2*j:22-2*j]
    assert remainder==norm[20:] and not roots
    builder.cx(norm[20],norm[21]);builder.x(norm[20])
    return norm

