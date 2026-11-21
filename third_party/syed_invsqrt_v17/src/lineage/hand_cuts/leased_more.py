"""Use the rank-one q11 lease on the second reachable guard that pays a later cubic."""
from leased import *
from leased import inject as first

def inject(src):
 s=first(src)
 gate='CCX q21 q17 q16\nCCZ q16 q7 q18\nCZ q16 q29\nCCX q21 q17 q16\nCZ q16 q29\n'
 assert s.count(gate)==1
 parked=['BIT_STORE1 b15012','HMR q11 b15010','Z q10 if b15010','Z q13 if b15010','Z q20 if b15010','Z q31 if b15010','CZ q10 q12 if b15010','CZ q10 q20 if b15010','CZ q10 q34 if b15010','CZ q12 q20 if b15010','CZ q12 q34 if b15010','CX q16 q11','CCX q21 q17 q11','CCZ q11 q7 q18','CZ q11 q29','CZ q16 q29','HMR q11 b15011','Z q16 if b15011','CZ q21 q17 if b15011']
 return s.replace(gate,'\n'.join(parked)+'\n')
if __name__=='__main__':
 par=pathlib.Path(sys.argv[1]) if len(sys.argv)>1 else P;out=pathlib.Path(sys.argv[2]) if len(sys.argv)>2 else H/'leased_more_native';out.mkdir(exist_ok=True,parents=True)
 before=par.read_text();after=inject(before);(out/'invsqrt.kmx').write_text(after);km.Circuit(after).to_file(str(out/'invsqrt.kmb'),format='kmb');F=lambda f:hashlib.sha256(f.read_bytes()).hexdigest();print('built',F(out/'invsqrt.kmb'),flush=True)
 k=sample(before,after);print('sample phases + cleanup',k,flush=True);(out/'certificate.json').write_text(json.dumps(dict(parent=F(par.with_suffix('.kmb')),child=F(out/'invsqrt.kmb'),exact_phase_and_cleanup_sample=k,lease_relative_to='leased_native'),indent=2)+'\n')
