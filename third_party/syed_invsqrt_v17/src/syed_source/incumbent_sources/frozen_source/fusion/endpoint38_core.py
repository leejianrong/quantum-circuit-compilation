# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.
"""A 27-wire routed phase endpoint with explicit cap-dependent hold schedules.

The caller supplies 26 quotient bits in increasing significance order and
four exponent flags. Every supplied wire is restored. A constant-one wire
and temporary AND owners are allocated and completely cleared here.
"""
from fractions import Fraction
import endpoint45_core as enc

N=27
CENTRES=(2,6,25,0,26)
CONTROLS=((0,4),(8,),(0,2,4,8),(0,1,2),(0,1))
HOLDS={(12,13):(0,2),(11,14):(0,3),(8,17):(3,6),(7,18):(4,7)}


def schedule(cap):
    assert cap in (44,45,46)
    if cap==46:return set(range(1,14)),set(range(13)),dict(HOLDS)
    if cap==45:return set(range(1,14))-{1,3,5},set(range(13)),{k:HOLDS[k] for k in ((11,14),(7,18))}
    return set(range(6,14)),set(range(1,13)),{}


def emit(d,b,word26,flags,angles,cap):
    assert len(word26)==26 and len(flags)==4 and len(angles)==35 and angles[-1]==0
    e_hold,f_hold,r_holds=schedule(cap)
    word=list(word26);one=b.alloc_qubits(1)[0];b.x(one);word.append(one)
    slots=[word[(j-5)%N] for j in range(N)]
    position_to_slot={(j-5)%N:j for j in range(N)}
    variables=list(flags)+[None];visited=set();held_e={};held_r={}
    def pairs(stage):return [(i,(CENTRES[stage]-i)%N) for i in range(N) if i<(CENTRES[stage]-i)%N]
    def swap_stage(stage,edges):
        with d._affine_control(b,variables,CONTROLS[stage]) as control:
            for left,right in edges:b.cswap(control,word[left],word[right])
    def hold(stage,edge):
        left,right=(word[i] for i in edge);anc=b.alloc_qubits(1)[0]
        with d._affine_control(b,variables,CONTROLS[stage]) as control:
            b.cx(left,right);b.ccx(control,right,anc);b.cx(left,right)
        b.cx(anc,left);b.cx(anc,right);return anc
    def release(stage,edge,anc):
        left,right=(word[i] for i in edge);b.cx(anc,left);b.cx(anc,right)
        outcome=b.alloc_bits(1)[0];b.hmr(anc,outcome)
        with d._affine_control(b,variables,CONTROLS[stage]) as control:
            b.push_condition(outcome);b.cz(control,left);b.cz(control,right);b.pop_condition()
        b.free(outcome);b.free(anc)
    def e_open(k):
        edge=(k,N-k)
        if k in e_hold:held_e[k]=hold(3,edge)
        else:swap_stage(3,[edge])
    def e_close(k):
        edge=(k,N-k)
        if k in e_hold:release(3,edge,held_e.pop(k))
        else:swap_stage(3,[edge])
    def feature(j):
        if j in enc.ENC:
            terms=enc.ENC[j];args=variables+[slots[j]];q=b.alloc_qubits(1)[0]
            d.xor_polynomial(b,args,q,terms)
            turns=Fraction(angles[N+j],1<<50) if j<7 else Fraction(1,8)
            b.z_pow(q,2*turns);d._erase_polynomial(b,q,args,terms)
        else:
            terms=enc.THR[j+1]
            if max(t.bit_count() for t in terms)<=1:
                with d._affine_control(b,variables,terms) as control:
                    d._feature(b,control,slots[j],Fraction(angles[N+j],1<<50) if j<7 else Fraction(1,4))
            else:
                q=b.alloc_qubits(1)[0];d.xor_polynomial(b,variables,q,terms)
                d._feature(b,q,slots[j],Fraction(angles[N+j],1<<50) if j<7 else Fraction(1,4))
                d._erase_polynomial(b,q,variables,terms)
    def visit(position):
        assert position not in visited;visited.add(position);j=position_to_slot[position]
        b.z_pow(word[position],Fraction(2*angles[j],1<<50))
        if j<=8:feature(j)
    def open_r(step):
        for edge,(start,stop) in r_holds.items():
            if start==step:held_r[edge]=hold(2,edge)
    def close_r(step):
        for edge,(start,stop) in r_holds.items():
            if stop==step:release(2,edge,held_r.pop(edge))
    late=[edge for edge in pairs(2) if edge not in r_holds]
    swap_stage(0,pairs(0));swap_stage(1,pairs(1));swap_stage(2,late)
    open_r(0);e_open(13);visit(13);close_r(0)
    for k in reversed(range(13)):
        step=13-k
        if step==9:
            p=b.alloc_qubits(1)[0];d.xor_polynomial(b,flags,p,(6,10));variables[4]=p
        open_r(step)
        if k:e_open(k)
        edge=(k,26-k)
        if k in f_hold:anc=hold(4,edge)
        else:swap_stage(4,[edge])
        visit(edge[0]);visit(edge[1])
        if k in f_hold:release(4,edge,anc)
        else:swap_stage(4,[edge])
        e_close(k+1);close_r(step)
    assert visited==set(range(N)) and not held_e and not held_r
    b.cz(flags[1],flags[3]);swap_stage(2,late);swap_stage(1,pairs(1));swap_stage(0,pairs(0))
    d._erase_polynomial(b,variables[4],flags,(6,10));b.x(one);b.free(one)


def check_routing():
    for exponent in range(11):
        f=[(exponent>>i)&1 for i in range(4)]
        active=[1^f[2],f[3],1^f[1]^f[2]^f[3],1^f[0]^f[1],1^f[0]]
        current=list(range(N))
        for stage,enabled in enumerate(active):
            if enabled:current=[current[(CENTRES[stage]-i)%N] for i in range(N)]
        assert all(current[(j-5)%N]==(j-exponent)%N for j in range(N))


check_routing()
