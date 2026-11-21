"""Absorb an earlier cubic into each of two mutually exclusive quartic branches and recycle their rank-one witness."""
import itertools,pathlib,sys,hashlib,json
from overlap import sample
import kickmix as km
H=pathlib.Path(__file__).resolve().parent;P=H.parent/'phase_agent/invsqrt.kmx'
S1='CCX q21 q7 q36\nCCZ q36 q18 q17\nCCX q21 q7 q36\n'
S2='CCX q21 q7 q36\nCCZ q36 q18 q17\nCX q29 q15\nCX q34 q15\nCZ q36 q15\nCCX q21 q7 q36\nCZ q36 q15\n'
A='CX q0 q18\nCX q7 q21\nCX q36 q21\nCCZ q17 q18 q21\n'

def inject(src):
 for key in (S1,S2,A):assert src.count(key)==1,key
 assert 'b15008' not in src
 # A fresh classical flag indicates that the original cubic was actually encountered.
 alive='BIT_STORE1 b15008\nBIT_STORE1 b15009\nBIT_STORE0 b15009 if b8004\nBIT_STORE0 b15009 if b8007\nCCZ q17 q18 q21 if b15009\n'
 src=src.replace(A,A.removesuffix('CCZ q17 q18 q21\n')+alive)
 for orig,extra in [(S1,False),(S2,True)]:
    # HMR the redundant target and remove its measurement sign with the exact rank-one witness.
    ops=['HMR q36 b15010','Z q0 if b15010','Z q8 if b15010','CZ q0 q8 if b15010','CZ q0 q30 if b15010','CZ q8 q30 if b15010',
         'CX q21 q36','CX q7 q36','CCX q21 q7 q36','CCZ q36 q18 q17']
    if extra:ops+=['CX q29 q15','CX q34 q15','CZ q36 q15','CZ q21 q15','CZ q7 q15']
    ops+=['HMR q36 b15011','Z q21 if b15011','Z q7 if b15011','CZ q21 q7 if b15011',
          'CX q0 q36','CX q8 q36','CX q30 q36','CX q30 q0','CX q30 q8','CCX q0 q8 q36','CX q30 q8','CX q30 q0']
    block='BIT_INVERT b15008\nPUSH_CONDITION if b15008\n'+orig+'POP_CONDITION\nBIT_INVERT b15008\nPUSH_CONDITION if b15008\n'+'\n'.join(ops)+'\nPOP_CONDITION\n'
    src=src.replace(orig,block)
 return src

def proof():
 n=0
 for bits in itertools.product(range(2),repeat=10):
    a,b,c,d,p,u,v,l,z,h=bits
    w=p^u^(p&u)^(p&v)^(u&v)
    assert w==(p^u^v^((p^v)&(u^v)))
    pre=w^a^b;orr=a^b^(a&b)
    old=((pre^(w^(a&b)))&c&d) ^ (l&a&b)
    new=(orr&c&d)^((orr^a^b)&l)
    sign=(z*w)^(z*p)^(z*u)^(z*p*u)^(z*p*v)^(z*u*v)^(h*orr)^(h*a)^(h*b)^(h*a*b)
    assert old==new and sign==0;n+=1
 return n
if __name__=='__main__':
 par=pathlib.Path(sys.argv[1]) if len(sys.argv)>1 else P;out=pathlib.Path(sys.argv[2]) if len(sys.argv)>2 else H/'quarter_native';out.mkdir(exist_ok=True,parents=True)
 before=par.read_text();after=inject(before);n=proof();(out/'invsqrt.kmx').write_text(after);km.Circuit(after).to_file(str(out/'invsqrt.kmb'),format='kmb')
 F=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();print('built',F(out/'invsqrt.kmb'),flush=True);s=sample(before,after);print('full phase + cleanup',s,flush=True)
 (out/'certificate.json').write_text(json.dumps(dict(parent=F(par.with_suffix('.kmb')),child=F(out/'invsqrt.kmb'),algebra=n,match_sample=s),indent=2)+'\n')
