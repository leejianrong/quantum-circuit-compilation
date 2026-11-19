# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Direct normalization94.75 emitter; no inherited module or source patching."""
from pathlib import Path
import hashlib, importlib.util, json, sys
HERE=Path(__file__).resolve().parent
NARROW=HERE.parents[3]
ACCEPTANCE=NARROW/'arithmetic_round2/receipts/NORMALIZATION9475_PAPER_ACCEPTED.json'
ACCEPTANCE_SHA='c6e795219c98415c078c010023004def1a76b2785779955c95d1f4f3c62f40bd'


def checked(path,digest):
    raw=path.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==digest,str(path)
    return json.loads(raw)


for pin in json.loads((HERE/'INPUTS.json').read_text())['files']:
    raw=(NARROW/pin['path']).read_bytes()
    assert len(raw)==pin['bytes']and hashlib.sha256(raw).hexdigest()==pin['sha256'],pin['path']
assert checked(ACCEPTANCE,ACCEPTANCE_SHA)['native_build_authorized']
path=NARROW/'research/quantized_producer/pair_normalization.py'
assert hashlib.sha256(path.read_bytes()).hexdigest()=='6af7fc14bc3c904efe480e2e23aee2fcbd97ad23f0a7ba324d8c05e1c8ec17fe'
spec=importlib.util.spec_from_file_location('_round2_rn2df_private_pair_normalizer',path)
old=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=old
spec.loader.exec_module(old)
km,cb=old.km,old.cb
MAX_X=old.MAX_X
from thermometer_cleanup import thermometer_matrix
FORWARD_ROWS=tuple(thermometer_matrix(10))
assert tuple(j for j,row in enumerate(FORWARD_ROWS,1)if(row>>6)&1)==(1,3,5,7)
MASKS=tuple(range(1,9))
FRAME=[['cx', 7, 6], ['cx', 7, 5], ['cx', 7, 4], ['cx', 7, 3], ['cx', 7, 2], ['cx', 7, 1], ['cx', 7, 0], ['cx', 6, 4], ['cx', 6, 2], ['cx', 6, 0], ['cx', 5, 4], ['cx', 5, 1], ['cx', 5, 0], ['cx', 4, 0], ['cx', 3, 2], ['cx', 3, 1], ['cx', 3, 0], ['cx', 2, 0], ['cx', 1, 0]]
CONTROLS=[{'first': 0, 'second': 1, 'terms': [1, 2, 3, 4, 5, 6, 7, 8]}, {'first': 2, 'second': 3, 'terms': [1, 2, 3, 4, 5, 6, 7, 8]}, {'first': 4, 'second': 5, 'terms': [1, 2, 3, 4, 5, 6, 7, 8]}, {'first': 6, 'second': 7, 'terms': [1, 2, 3, 4, 5, 6, 7, 8]}, {'first': 8, 'second': 9, 'terms': [1, 2, 3, 4, 5, 6, 7, 8]}, {'first': 0, 'second': 2, 'terms': [1, 3, 5, 7]}, {'first': 1, 'second': 3, 'terms': [2, 4, 6, 8]}, {'first': 4, 'second': 6, 'terms': [1, 3, 5, 7]}, {'first': 5, 'second': 7, 'terms': [2, 4, 6, 8]}, {'first': 8, 'second': 10, 'terms': [1, 3, 5, 7]}, {'first': 0, 'second': 4, 'terms': [1, 5]}, {'first': 1, 'second': 5, 'terms': [2, 6]}, {'first': 2, 'second': 6, 'terms': [3, 7]}, {'first': 3, 'second': 7, 'terms': [4, 8]}, {'first': 0, 'second': 8, 'terms': [1]}, {'first': 1, 'second': 9, 'terms': [2]}, {'first': 2, 'second': 10, 'terms': [3]}]

def route_lane(builder,lane,T):
    count=0
    for op in old.operations(len(lane)):
        terms=[i for i in op['prefix_terms'] if i<=10]
        assert terms and 0 not in terms
        control=T[terms[0]-1];others=[T[i-1]for i in terms[1:]]
        for q in others:builder.cx(q,control)
        builder.cswap(control,lane[op['first']],lane[op['second']]);count+=1
        for q in reversed(others):builder.cx(q,control)
    assert count=={10:15,11:17}[len(lane)]


def forward(builder,x,flags):
    x=list(x);flags=list(flags);P=[]
    assert len(x)==22 and len(flags)==4
    for length in range(1,21):
        q=builder.alloc_qubits(1)[0];data=x[22-length]
        if length==1:builder.x(q);builder.cx(data,q)
        elif length==2:builder.cx(P[-1],q);builder.cx(data,q)
        else:builder.x(data);builder.ccx(P[-1],data,q);builder.x(data)
        P.append(q)
    T=P[1::2]
    for bit,flag in enumerate(flags):
        for j in range(1<<bit,11,1<<bit):builder.cx(T[j-1],flag)
    for position in range(2,22):
        for prefix in(21-position,22-position):
            if prefix==0:builder.x(x[position])
            else:builder.cx(P[prefix-1],x[position])
    builder.x(x[21])
    for q in P:builder.cx(q,x[21])
    builder.x(x[1]);builder.ccx(T[-1],x[1],x[21]);builder.x(x[1])
    for target,prefixes in((x[0],P),(x[1],P[:-1])):
        builder.x(target);builder.cx(x[21],target)
        for q in prefixes:builder.cx(q,target)
    route_lane(builder,x[0::2],T);route_lane(builder,x[1:21:2],T)
    builder.x(x[20]);builder.cx(x[21],x[20])
    for j in range(1,11):
        q=P[2*j-2];m=builder.alloc_bits(1)[0];builder.hmr(q,m)
        if j==1:cb.emit_phase(builder,[T[0],x[21]],m,old.ODD_FIRST)
        else:cb.emit_phase(builder,[T[j-2],T[j-1],x[21]],m,old.ODD_OTHER)
        builder.free(m);builder.free(q)
    parity=builder.alloc_bits(1)[0];builder.bit_store(parity,False)
    for q,row in zip(T,FORWARD_ROWS):
        outcome=builder.alloc_bits(1)[0];builder.hmr(q,outcome)
        builder.push_condition(outcome)
        for mask in range(1,11):
            if ((row>>(mask-1))&1)==0 or mask==7:continue
            controls=[flags[i]for i in range(4)if(mask>>i)&1]
            if len(controls)==1:builder.z(controls[0])
            else:assert len(controls)==2;builder.cz(*controls)
        builder.pop_condition()
        if(row>>(7-1))&1:builder.cx(outcome,parity)
        builder.free(outcome);builder.free(q)
    builder.push_condition(parity);builder.ccz(*flags[:3]);builder.pop_condition();builder.free(parity)


def prepare(builder, flags):
    monomials = {1 << i: q for i, q in enumerate(flags)}
    helpers = []
    for mask in MASKS:
        if mask in monomials:
            continue
        low = mask & -mask
        q = builder.alloc_qubits(1)[0]
        builder.ccx(monomials[mask ^ low], monomials[low], q)
        monomials[mask] = q
        helpers.append(q)
    assert len(helpers) == 4
    wires = [monomials[m] for m in MASKS]
    for name, a, b in FRAME:
        if name == 'cx':
            builder.cx(wires[a], wires[b])
        else:
            builder.swap(wires[a], wires[b])
    return dict(zip(range(1, 9), wires)), helpers


def measured(builder, q, role=None):
    outcome = builder.alloc_bits(1)[0]
    if role is not None and hasattr(builder, 'select_outcome'):
        builder.select_outcome(outcome, role)
    builder.hmr(q, outcome)
    return outcome


def prefix_phase(builder, outcome, previous, a, b):
    builder.push_condition(outcome)
    builder.z(previous)
    builder.cz(previous, a)
    builder.cz(previous, b)
    builder.ccz(previous, a, b)
    builder.pop_condition()


def joint_last_phase(builder, x, mB, m3, *, omit_final_helper_fix=False):
    # Both raw complement frames and the affine T1 frame are restored below.
    builder.cx(x[21], x[20])
    builder.x(x[20])
    for i in (18, 19, 16, 17):
        builder.x(x[i])
    a, t2 = list(builder.alloc_qubits(2))
    ma, mt = list(builder.alloc_bits(2))
    builder.bit_store(ma, False)
    builder.bit_store(mt, False)
    builder.push_condition(m3)
    builder.ccx(x[20], x[18], a)
    builder.ccx(a, x[19], t2)
    builder.push_condition(mB)
    builder.z(t2)
    builder.pop_condition()
    builder.ccz(t2, x[16], x[17])
    builder.hmr(t2, mt)
    builder.push_condition(mt)
    builder.cz(a, x[19])
    builder.pop_condition()
    builder.hmr(a, ma)
    builder.push_condition(ma)
    if not omit_final_helper_fix:
        builder.cz(x[20], x[18])
    builder.pop_condition()
    builder.pop_condition()
    builder.free(mt)
    builder.free(ma)
    builder.free(t2)
    builder.free(a)
    builder.x(m3)
    builder.push_condition(m3)
    builder.push_condition(mB)
    builder.ccz(x[20], x[18], x[19])
    builder.pop_condition()
    builder.pop_condition()
    builder.x(m3)
    for i in (17, 16, 19, 18):
        builder.x(x[i])
    builder.x(x[20])
    builder.cx(x[21], x[20])


def inverse(builder, x, flags, *, omit_final_helper_fix=False):
    x, flags = list(x), list(flags)
    T, helpers = prepare(builder, flags)
    for operation in reversed(CONTROLS):
        terms = operation['terms']
        control, others = T[terms[0]], [T[j] for j in terms[1:]]
        for q in others:
            builder.cx(q, control)
        for lane in range(2):
            builder.cswap(control, x[2*operation['first'] + lane], x[2*operation['second'] + lane])
        for q in reversed(others):
            builder.cx(q, control)
    A = T.pop(1)
    builder.x(A)
    builder.cx(x[20], A)
    builder.cx(x[21], A)
    T[9] = A
    mB = measured(builder, T.pop(2), 'B')
    prefix_phase(builder, mB, T[9], x[2], x[3])
    for j in reversed(range(4, 10)):
        outcome = measured(builder, T[j])
        prefix_phase(builder, outcome, T[j-1], x[22-2*j], x[23-2*j])
        builder.free(outcome)
    m3 = measured(builder, T[3], 'T3')
    builder.free(km.array(helpers))
    joint_last_phase(builder, x, mB, m3, omit_final_helper_fix=omit_final_helper_fix)
    builder.free(mB)
    builder.free(m3)


CONTRACT=dict(component_E=94.75,forward_E=51.5,inverse_E=43.25,local_peak=46,
    global_Q=48,forward_boundary_owners=26,inverse_boundary_owners=26,
    T=0,R=0,exact_numeric_phase_change=0,protected_phase_loaders_unchanged=True)
