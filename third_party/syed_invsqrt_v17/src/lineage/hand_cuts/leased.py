"""Extend the rank-one lease through later use of the same paid q17*q0 product."""
from quarter_merge import *
from quarter_merge import inject as first

def inject(src):
 s=first(src)
 start='HMR q36 b15010\n'; end='CCX q0 q8 q36\nCX q30 q8\nCX q30 q0\n'
 begin=s.rindex(start);finish=s.index(end,begin)+len(end)
 q_terms=[(10,),(13,),(20,),(31,),(10,12),(10,20),(10,34),(12,20),(12,34)]
 z=lambda j:'q'+str(j)
 lease=['BIT_STORE1 b15012','HMR q11 b15010']+[' '.join(['Z' if len(r)==1 else 'CZ',*map(z,r),'if','b15010']) for r in q_terms]
 lease+=['CX q21 q11','CX q7 q11','CCX q21 q7 q11','CCZ q11 q18 q17','CX q29 q15','CX q34 q15','CZ q11 q15','CZ q21 q15','CZ q7 q15','HMR q11 b15011','Z q21 if b15011','Z q7 if b15011','CZ q21 q7 if b15011']
 s=s[:begin]+'\n'.join(lease)+'\n'+s[finish:]
 # Parked episodes have a clean q11 and no other use before the restore.
 marker='PUSH_CONDITION if b361\nPUSH_CONDITION if b366\nCX q15 q8\nCX q30 q8\nCX q34 q8\nCX q36 q8\nCCZ q17 q0 q8\n'
 assert s.count(marker)==1;s=s.replace(marker,'CCX q17 q0 q11 if b15012\n'+marker)
 for p in (7,8):
    gate=f'CCZ q17 q0 q{p}\n';m=marker if p==8 else 'CX q16 q7\nCX q18 q7\nCX q29 q7\nCX q30 q7\nCX q34 q7\nCX q36 q7\n'+gate
    assert s.count(m)==1
    rep=f'CZ q11 q{p} if b15012\nBIT_INVERT b15012\nCCZ q17 q0 q{p} if b15012\nBIT_INVERT b15012\n'
    s=s.replace(m,m.removesuffix(gate)+rep)
 tail='HMR q36 b984\nPUSH_CONDITION if b361\nCX q17 q36\nCX q7 q36\nCX q18 q36\nCX q21 q36\nCCX q17 q0 q36\nPOP_CONDITION\n'
 assert s.count(tail)==1
 payoff=['PUSH_CONDITION if b15012','HMR q11 b15013','CZ q17 q0 if b15013',
        'CX q13 q11','CX q20 q11','CX q31 q11','CX q10 q12','CX q10 q20','CX q34 q20','CCX q12 q20 q11','CX q34 q20','CX q10 q20','CX q10 q12','POP_CONDITION']
 rep='CX q11 q36 if b15012\nBIT_INVERT b15012\nCCX q17 q0 q36 if b15012\nBIT_INVERT b15012\nPOP_CONDITION\n'+'\n'.join(payoff)+'\n'
 s=s.replace(tail,tail.removesuffix('CCX q17 q0 q36\nPOP_CONDITION\n')+rep)
 return s

def proof_lease():
 for a,b,c,d,e,h in itertools.product(range(2),repeat=6):
    old=a^d^c^h^(a&b)^(a&c)^(a&e)^(b&c)^(b&e)
    assert old==d^c^h^((a^b)&(a^c^e))
if __name__=='__main__':
 par=pathlib.Path(sys.argv[1]) if len(sys.argv)>1 else P;out=pathlib.Path(sys.argv[2]) if len(sys.argv)>2 else H/'leased_native';out.mkdir(exist_ok=True,parents=True)
 before=par.read_text();after=inject(before);proof_lease();(out/'invsqrt.kmx').write_text(after);km.Circuit(after).to_file(str(out/'invsqrt.kmb'),format='kmb');F=lambda f:hashlib.sha256(f.read_bytes()).hexdigest();print('built',F(out/'invsqrt.kmb'),flush=True)
 k=sample(before,after);print('sample phases + cleanup',k,flush=True);(out/'certificate.json').write_text(json.dumps(dict(parent=F(par.with_suffix('.kmb')),child=F(out/'invsqrt.kmb'),exact_phase_and_cleanup_sample=k,lease_relative_to='quarter_native'),indent=2)+'\n')
