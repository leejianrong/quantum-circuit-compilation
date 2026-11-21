# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""One paid-C10 recoding and two CCZs, with retained-C9 Clifford erasure.

Raw control order: v8,v9,v10,v11,R9,R10,s13,C9. Recode C10 to
H=C10 XOR v8*(v10 XOR R10). The complete remaining phase is F.
"""
from pathlib import Path
import hashlib,json
NOTICE='Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0. Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.'
ORDER=('v8','v9','v10','v11','R9','R10','s13','C9','C10')
BANK=(1,36);L=14;CDE=((70,146,158),(0,246,9))
# The original Q_before has three C10*L terms. Adding C10*L to replace
# AB*L by H*L cancels those three terms, leaving these thirteen free gates.
BEFORE=((1,),(7,),(0,1),(0,5),(0,6),(1,2),(1,4),(1,6),(1,7),(2,4),(4,6),(4,7),(4,8))
ORIGINAL_BEFORE=((1,),(7,),(0,1),(0,5),(0,6),(1,2),(1,4),(1,6),(1,7),(1,8),(2,4),(2,8),(3,8),(4,6),(4,7),(4,8))
def owners(v,R9,R10,sign,C9,C10):return [v[8],v[9],v[10],v[11],R9,R10,sign,C9,C10]
def before(builder,v,R9,R10,sign,C9,C10):
    wires=owners(v,R9,R10,sign,C9,C10)
    for term in BEFORE:
        if len(term)==1:builder.z(wires[term[0]])
        else:builder.cz(wires[term[0]],wires[term[1]])
def capture(builder,v,R10,C10):
    builder.cx(R10,v[10]);builder.ccx(v[8],v[10],C10);builder.cx(R10,v[10])
def phase(builder,v,R9,R10,sign,C9,H):
    # First CCZ: (H+v9+v10+s)*(v9+R9+C9)*(v9+v10+v11+R9+C9).
    for q in (v[9],v[10],sign):builder.cx(q,H)
    builder.cx(R9,v[9]);builder.cx(C9,v[9])
    builder.cx(v[9],v[10]);builder.cx(v[11],v[10])
    builder.ccz(H,v[9],v[10])
    builder.cx(v[11],v[10]);builder.cx(v[9],v[10])
    builder.cx(C9,v[9]);builder.cx(R9,v[9])
    for q in (sign,v[10],v[9]):builder.cx(q,H)
    # Second CCZ: H*(v9+v10+R9+R10+s+C9)*(v8+v11).
    for q in (v[10],R9,R10,sign,C9):builder.cx(q,v[9])
    builder.cx(v[11],v[8]);builder.ccz(H,v[9],v[8]);builder.cx(v[11],v[8])
    for q in (C9,sign,R10,R9,v[10]):builder.cx(q,v[9])
    # The free post-recoding phase H*L accounts for the original AB*L.
    for q in (v[9],v[10],v[11]):builder.cz(H,q)
def feedback(builder,v,R9,R10,sign,C9):
    # old C10 = MAJ(v10, 1+s+R9, C9); added product is quadratic.
    builder.cx(sign,R9);builder.x(R9)
    builder.cz(v[10],R9);builder.cz(v[10],C9);builder.cz(R9,C9)
    builder.x(R9);builder.cx(sign,R9)
    builder.cz(v[8],v[10]);builder.cz(v[8],R10)
def self_check():
    class Replay:
        def __init__(self,x):self.values=[x>>i&1 for i in range(9)];self.phase=0;self.ccx_count=0;self.ccz_count=0
        def x(self,a):self.values[a]^=1
        def cx(self,a,b):self.values[b]^=self.values[a]
        def ccx(self,a,b,c):self.values[c]^=self.values[a]&self.values[b];self.ccx_count+=1
        def ccz(self,a,b,c):self.phase^=self.values[a]&self.values[b]&self.values[c];self.ccz_count+=1
        def z(self,a):self.phase^=self.values[a]
        def cz(self,a,b):self.phase^=self.values[a]&self.values[b]
    v=[None]*8+[0,1,2,3];phase_values=[]
    for x in range(512):
        r=Replay(x);before(r,v,4,5,6,7,8);capture(r,v,5,8);phase(r,v,4,5,6,7,8)
        parity=lambda m:(x&m).bit_count()&1;P=parity(BANK[0])&parity(BANK[1]);H=(x>>8&1)^P
        wanted=(P&parity(L))
        for c,d,e in CDE:wanted^=(H^parity(c))&parity(d)&parity(e)
        for term in ORIGINAL_BEFORE:
            wanted^=int(all(x>>i&1 for i in term))
        assert r.phase==wanted and r.values==[x>>i&1 for i in range(8)]+[H]
        assert r.ccx_count==1 and r.ccz_count==2
        phase_values.append(wanted)
    for x in range(256):
        a=x>>2&1;u=1^(x>>6&1)^(x>>4&1);c=x>>7&1;old=(a&u)^(a&c)^(u&c);P=(x&1)&(((x>>2)^(x>>5))&1)
        r=Replay(x);feedback(r,v,4,5,6,7);assert r.phase==old^P and r.values==[x>>i&1 for i in range(9)] and not r.ccx_count and not r.ccz_count
    from row13_chart import get_chart
    chart=get_chart(0,kind='carry');ns=chart['early_names']
    for j,code in enumerate(chart['early']):
        env={name:code>>i&1 for i,name in enumerate(ns)};env['C10']=env['C10_dirty'];env['R10']=env['B1']^env['s13']^env['v11']^env['C10']
        x=sum(env[name]<<i for i,name in enumerate(ORDER));assert phase_values[x]==(chart['target']>>j&1)
    out=dict(notice=NOTICE,status='LITERAL_CAPTURE_PHASE_FEEDBACK_AND_CARE_PASS',source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),independent_phase_cases=512,independent_feedback_cases=256,care_rows=len(chart['early']),quantum_data_restored=True,recoding_CCX=1,phase_CCZ=2,feedback_CCX=0,constant_omitted=False,phase_target='K*(R11 XOR s13)',full_native_proof=False)
    Path(__file__).with_suffix('.algebra.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
if __name__=='__main__':self_check()
