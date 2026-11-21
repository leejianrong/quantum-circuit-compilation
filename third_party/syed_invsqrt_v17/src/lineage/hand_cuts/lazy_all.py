"""Lease and lazily retire q31 in all four large inverse phase-bank sectors."""
from lazy_lease import *
from lazy_lease import inject as prior

def inject(src):
 s=prior(src)
 # Extract the already-tested q31 phase erasure from the previous sector.
 start=s.index('BIT_STORE1 b15012\nHMR q31 b15010\n');end=s.index('CX q16 q31\n',start);head=s[start:end]
 assert head.count('HMR')==1 and 'CCX' not in head
 # b8004 uses the same OR as b8007, with a shorter phase suffix.
 a=s.index('HMR q36 b15010\n');tail='CCX q0 q8 q36\nCX q30 q8\nCX q30 q0\n';z=s.index(tail,a)+len(tail)
 v=['CX q21 q31','CX q7 q31','CCX q21 q7 q31','CCZ q31 q18 q17','HMR q31 b15011','Z q21 if b15011','Z q7 if b15011','CZ q21 q7 if b15011']
 s=s[:a]+head+'\n'.join(v)+'\n'+s[z:]
 # b8006 mirrors b8005 with q0 taking the dirty target role of q16.
 gate='CCX q21 q17 q0\nCCZ q0 q7 q18\nCZ q0 q29\nCCX q21 q17 q0\nCZ q0 q29\n';assert s.count(gate)==1
 block=['CX q0 q31','CCX q21 q17 q31','CCZ q31 q7 q18','CZ q31 q29','CZ q0 q29','HMR q31 b15011','Z q0 if b15011','CZ q21 q17 if b15011']
 return s.replace(gate,head+'\n'.join(block)+'\n')
if __name__=='__main__':
 par=pathlib.Path(sys.argv[1]) if len(sys.argv)>1 else P;out=pathlib.Path(sys.argv[2]) if len(sys.argv)>2 else H/'lazy_all_native';out.mkdir(exist_ok=True,parents=True)
 before=par.read_text();after=inject(before);(out/'invsqrt.kmx').write_text(after);km.Circuit(after).to_file(str(out/'invsqrt.kmb'),format='kmb');F=lambda f:hashlib.sha256(f.read_bytes()).hexdigest();print('built',F(out/'invsqrt.kmb'),flush=True)
 k=sample(before,after);print('sample phases + cleanup',k,flush=True);(out/'certificate.json').write_text(json.dumps(dict(parent=F(par.with_suffix('.kmb')),child=F(out/'invsqrt.kmb'),exact_phase_and_cleanup_sample=k,relative_to='lazy_native'),indent=2)+'\n')
