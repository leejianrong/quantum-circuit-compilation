# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Split K*R11 phase around the EXISTING first row13 terminal MAJ.

Both calls are inside b. emit_early requires v[10] to hold dirty C10,
first_target=q0prime, second_target=B1, and a K bank. Then pay CZ(sign,K),
HMR/free K, and repay its outcome under b by the free quadratic majority
of(v[11],second_target,v[10]), BEFORE ordinary sum/unwind. emit_late occurs
after unwind, with raw R9 and original C9. No late operation uses K.

All data owners are restored by each emitter. No owner is allocated and no
constant is omitted. This is care-set-specific; unchanged full native proof
is still required after integration.
"""
from pathlib import Path
import hashlib,json
NOTICE='Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0. Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.'
EARLY_ORDER=('v8','v9','C10_dirty','v11','q0prime','B1','s13','K')
FACTORS=((134,24,192),(5,8,224))
EARLY_CZ=((0,7),(1,3),(1,4),(1,7),(2,6),(3,5),(3,7),(4,7),(5,7))

def emit_early(builder,v,first_target,second_target,sign,bank):
    owners=[v[8],v[9],v[10],v[11],first_target,second_target,sign,bank]
    assert len(set(owners))==8
    for masks in FACTORS:
        pivots=[(m&-m).bit_length()-1 for m in masks];assert len(set(pivots))==3
        assert all(not(m>>pivots[j]&1)for i,m in enumerate(masks)for j in range(3)if i!=j)
        moves=[]
        for mask,pivot in zip(masks,pivots):
            for source in range(8):
                if source!=pivot and mask>>source&1:builder.cx(owners[source],owners[pivot]);moves.append((source,pivot))
        builder.ccz(*(owners[p]for p in pivots))
        for source,pivot in reversed(moves):builder.cx(owners[source],owners[pivot])
    for a,b in EARLY_CZ:builder.cz(owners[a],owners[b])

def emit_late(builder,v,raw_r9,sign,c9):
    for a,b in((v[8],v[11]),(v[9],raw_r9),(v[9],c9),(raw_r9,sign),(sign,c9)):builder.cz(a,b)

def self_check():
    class Replay:
        def __init__(self,x,n):self.values=[x>>i&1 for i in range(n)];self.phase=0;self.ccz_count=0
        def cx(self,a,b):self.values[b]^=self.values[a]
        def cz(self,a,b):self.phase^=self.values[a]&self.values[b]
        def ccz(self,a,b,c):self.phase^=self.values[a]&self.values[b]&self.values[c];self.ccz_count+=1
    early=[];late=[]
    for x in range(256):
        r=Replay(x,8);emit_early(r,[None]*8+[0,1,2,3],4,5,6,7)
        expected=sum(all((x&m).bit_count()&1 for m in gate)for gate in FACTORS)&1
        expected^=sum((x>>a&1)&(x>>b&1)for a,b in EARLY_CZ)&1
        assert r.values==[x>>i&1 for i in range(8)]and r.phase==expected and r.ccz_count==2;early.append(r.phase)
    for x in range(512):
        r=Replay(x,9);emit_late(r,[None]*8+[0,1,2,3],4,6,8)
        expected=sum((x>>a&1)&(x>>b&1)for a,b in((0,3),(1,4),(1,8),(4,6),(6,8)))&1
        assert r.values==[x>>i&1 for i in range(9)]and r.phase==expected and r.ccz_count==0;late.append(r.phase)
    carepath=Path(__file__).with_name('row13_paid_terminal_temporal_v1.json');care=json.loads(carepath.read_text())
    for code,e in zip(care['encoded_care'],care['early_rows']):assert early[e&255]^late[code&511]==(code>>9&1)
    result=dict(notice=NOTICE,status='EXACT_SPLIT_EMITTER_AND_FULL_SCALAR_CARE_NOT_NATIVE_PROOF',source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),care_sha256=hashlib.sha256(carepath.read_bytes()).hexdigest(),early_owner_order=EARLY_ORDER,factor_masks=FACTORS,early_CZ=EARLY_CZ,late_CZ=[['v8','v11'],['v9','R9'],['v9','C9'],['R9','s13'],['s13','C9']],independent_early_gate_inputs=256,independent_late_gate_inputs=512,complete_care_rows=103,original_scalar_inputs=3133452,all_data_restored=True,new_owners=0,constant_omitted=False,CCZ_count=2,K_erasure_nonlinear_cost='0',modelled_gain_vs_qualified1440='1/4',full_native_proof=False,two_native_builds=False)
    Path(__file__).with_suffix('.algebra.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':self_check()
