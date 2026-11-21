# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.
"""Outcome-selected one-AND bank and one-CCZ high phase, Hq XOR1.

The caller places all functions under mB. For q=0 bank=C10; for q=1
bank=A*B on the unsummed terminal chart. Capture costs one CCX either way.
Early phase costs one CCZ either way. Both banks have free quadratic HMR
feedback BEFORE terminal SUM. q1 has no late phase; q0 keeps two late CZs.
The explicit raw mB constant cancels the deliberately omitted1 in Hq XOR1.
"""
from pathlib import Path
import hashlib,json
NOTICE='Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0. Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.'
EARLY_ORDER=('v6','v7','v8','v9','v10','v11','I8','pre9','C8','C9','s12')
A,B,C,D,E,L=1196,1168,1070,1038,16,138
Q1_FREE=(2,4,8,16,32,512,1024,6,34,514,12,36,24,136,520,144,528,160,640,1152)
Q0_FACTORS=(37,6,360)
Q0_FREE=(2,4,8,32,64,128,5,33,65,129,6,10,66,130,12,36)

def _early(v,pre9,C9,sign):
    return [v[6],v[7],v[8],v[9],v[10],v[11],None,pre9,None,C9,sign]

def _reframe(builder,owners,masks):
    pivots=[(m&-m).bit_length()-1 for m in masks];assert len(set(pivots))==len(pivots)
    assert all(not(m>>pivots[j]&1)for i,m in enumerate(masks)for j in range(len(masks))if i!=j)
    moves=[]
    for m,p in zip(masks,pivots):
        for i in range(len(owners)):
            if i!=p and m>>i&1:
                assert owners[i]is not None;builder.cx(owners[i],owners[p]);moves.append((i,p))
    return [owners[p]for p in pivots],moves

def _undo(builder,owners,moves):
    for i,p in reversed(moves):builder.cx(owners[i],owners[p])

def _free(builder,owners,masks):
    for m in masks:
        wires=[owners[i]for i in range(len(owners))if m>>i&1];assert all(w is not None for w in wires)
        if len(wires)==1:builder.z(wires[0])
        elif len(wires)==2:builder.cz(*wires)
        else:raise AssertionError(m)

def _q0(builder,q):builder.x(q);builder.push_condition(q)
def _endq0(builder,q):builder.pop_condition();builder.x(q)

def capture(builder,v,pre9,C9,sign,bank,q_classical):
    _q0(builder,q_classical)
    a,c,t=v[10],C9,pre9
    builder.cx(c,a);builder.cx(c,t);builder.ccx(a,t,bank);builder.cx(c,bank);builder.cx(c,t);builder.cx(c,a)
    _endq0(builder,q_classical)
    builder.push_condition(q_classical);owners=_early(v,pre9,C9,sign)
    pivots,moves=_reframe(builder,owners,(A,B));builder.ccx(*pivots,bank);_undo(builder,owners,moves);builder.pop_condition()

def emit_early(builder,v,raw_I8,pre9,C9,sign,bank,q_classical):
    _q0(builder,q_classical)
    owners=[v[7],v[8],v[9],v[10],v[11],pre9,C9,sign,bank]
    pivots,moves=_reframe(builder,owners,Q0_FACTORS);builder.ccz(*pivots);_undo(builder,owners,moves);_free(builder,owners,Q0_FREE)
    _endq0(builder,q_classical)
    builder.push_condition(q_classical);owners=_early(v,pre9,C9,sign)
    for i,wire in enumerate(owners):
        if C>>i&1:builder.cx(wire,bank)
    pivots,moves=_reframe(builder,owners,(D,E));builder.ccz(bank,*pivots);_undo(builder,owners,moves)
    for i,wire in reversed(list(enumerate(owners))):
        if C>>i&1:builder.cx(wire,bank)
    for i,wire in enumerate(owners):
        if L>>i&1:builder.cz(bank,wire)
    _free(builder,owners,Q1_FREE);builder.pop_condition()

def phase_bank(builder,v,pre9,C9,sign,q_classical):
    """Call under the bank's HMR outcome, before changing the terminal inputs."""
    _q0(builder,q_classical)
    for a,b in((v[10],pre9),(v[10],C9),(pre9,C9)):builder.cz(a,b)
    _endq0(builder,q_classical)
    builder.push_condition(q_classical);owners=_early(v,pre9,C9,sign)
    pivots,moves=_reframe(builder,owners,(A,B));builder.cz(*pivots);_undo(builder,owners,moves);builder.pop_condition()

def emit_late(builder,v,raw_I8,raw_I9,I10,C9,sign,q_classical):
    _q0(builder,q_classical);builder.cz(v[7],I10);builder.cz(v[10],I10);_endq0(builder,q_classical)

class Replay:
    def __init__(self,x,q):self.values=[x>>i&1 for i in range(12)];self.q=q;self.conditions=[];self.phase=0;self.ccx_count=0;self.ccz_count=0
    def active(self):return all(self.conditions)
    def push_condition(self,q):assert q=='q';self.conditions.append(bool(self.q))
    def pop_condition(self):self.conditions.pop()
    def x(self,q):assert q=='q';self.q^=1
    def cx(self,a,b):
        if self.active():self.values[b]^=self.values[a]
    def ccx(self,a,b,c):
        if self.active():self.values[c]^=self.values[a]&self.values[b];self.ccx_count+=1
    def z(self,a):
        if self.active():self.phase^=self.values[a]
    def cz(self,a,b):
        if self.active():self.phase^=self.values[a]&self.values[b]
    def ccz(self,a,b,c):
        if self.active():self.phase^=self.values[a]&self.values[b]&self.values[c];self.ccz_count+=1

def self_check():
    v=[None]*6+list(range(6));early_phases=[[],[]];bank_values=[[],[]]
    for q in(0,1):
        for x in range(2048):
            sim=Replay(x,q);capture(sim,v,7,9,10,11,'q')
            bank=sim.values[11];expected=((x&A).bit_count()&1)&((x&B).bit_count()&1)if q else((x>>4&1)&(x>>7&1))^((x>>4&1)&(x>>9&1))^((x>>7&1)&(x>>9&1))
            assert bank==expected and sim.values[:11]==[x>>i&1 for i in range(11)]and sim.q==q and sim.ccx_count==1
            emit_early(sim,v,6,7,9,10,11,'q');assert sim.values==[x>>i&1 for i in range(11)]+[bank]and sim.q==q and sim.ccz_count==1
            early_phases[q].append(sim.phase);bank_values[q].append(bank)
            for outcome in(0,1):
                correction=Replay(x,q)
                if outcome:phase_bank(correction,v,7,9,10,'q')
                assert correction.phase==(outcome&bank)and correction.values==[x>>i&1 for i in range(12)]and correction.q==q
    late_phases=[[],[]]
    for q in(0,1):
        for x in range(4096):
            sim=Replay(x,q);emit_late(sim,v,6,7,8,10,11,'q');assert sim.values==[x>>i&1 for i in range(12)]and sim.q==q;late_phases[q].append(sim.phase)
    carefile=Path(__file__).with_name('row12_early_bank_phase_screen.json');care=json.loads(carefile.read_text());cases=0
    for q,index in((0,1),(1,3)):
        for code in care['local_tables'][index]['encoded_care']:
            x=code&2047;lo,u,w,r,a,z,i8,pre,c8,c,s=[x>>i&1 for i in range(11)];i9=s^a^pre^c;i10=a^w^u^((u^i9)&(r^i9));y=sum(bit<<i for i,bit in enumerate([lo,u,w,r,a,z,i8,i9,i10,c8,c,s]))
            assert early_phases[q][x]^late_phases[q][y]==((code>>12&1)^1);cases+=1
    record=dict(notice=NOTICE,status='EXACT_LITERAL_QUADRATIC_BANK_EMITTER_NOT_NATIVE_PROOF',source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),care_sha256=hashlib.sha256(carefile.read_bytes()).hexdigest(),phase_convention='Hq XOR1; omitted1 cancels explicit raw mB constant',early_capture_phase_cases=4096,bank_HMR_feedback_cases=8192,late_cases=8192,complete_care_cases=cases,original_inputs=3133452,quantum_owners_restored=True,classical_q_restored=True,capture_CCX_each_q=1,phase_CCZ_each_q=1,HMR_feedback_nonlinear_cost=0,additional_clean_owners=0,modelled_gain_vs_qualified1438p25='1/4',full_native_proof=False)
    Path(__file__).with_suffix('.algebra.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2))
if __name__=='__main__':self_check()
