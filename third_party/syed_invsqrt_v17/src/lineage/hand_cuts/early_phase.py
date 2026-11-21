"""Evaluate the b8006 quartic at the earlier carry stage where q8 is a native clean target."""
from lazy_all import *
from lazy_all import inject as prior

def inject(src):
 s=prior(src);g='PUSH_CONDITION if b8006\n';l=s.index(g);a=s.index('BIT_STORE1 b15012\nHMR q31 b15010\n',l);ending='HMR q31 b15011\nZ q0 if b15011\nCZ q21 q17 if b15011\n';z=s.index(ending,a)+len(ending);assert '\nCCZ q31 q7 q18\n' in s[a:z];s=s[:a]+s[z:]
 # At 18693, A=q21, B=q0+q17+q18+q34, C=q7+q21+q34, D=q0+q7+q18+q29+q34.
 # q8 starts at zero. T=q0+q17+q21+q34 and E=q29. The phase is (T+AB)CD+ABE, over GF(2).
 T=[0,17,21,34];B=[0,17,18,34];prepB=['CX q0 q17','CX q18 q17','CX q34 q17'];prepD=['CX q0 q18','CX q7 q18','CX q29 q18','CX q34 q18'];prepC=['CX q21 q7','CX q34 q7'];
 b=['BIT_INVERT b364','PUSH_CONDITION if b365','PUSH_CONDITION if b363','PUSH_CONDITION if b364'];b+= [f'CX q{k} q8' for k in T]+prepB+['CCX q21 q17 q8']+prepB[::-1]+prepD+prepC+['CCZ q8 q7 q18']+prepC[::-1]+prepD[::-1]+['CZ q8 q29']+[f'CZ q{k} q29' for k in T]+['HMR q8 b15018']+[f'Z q{k} if b15018' for k in T]+[f'CZ q21 q{k} if b15018' for k in B]+['POP_CONDITION','POP_CONDITION','POP_CONDITION','BIT_INVERT b364']
 # The CNOTs on q11 and q27 preceding this anchor do not touch our coordinates.
 tag='CX q36 q11\nCX q36 q27\nCCX q11 q27 q8\n';ix=s.index(tag,s.index('BIT_STORE0 b365\n'));assert ix>=0
 s=s[:ix]+s[ix:].replace(tag,tag.removesuffix('CCX q11 q27 q8\n')+'\n'.join(b)+'\nCCX q11 q27 q8\n',1)
 return s
if __name__=='__main__':
 par=pathlib.Path(sys.argv[1]) if len(sys.argv)>1 else P;out=pathlib.Path(sys.argv[2]) if len(sys.argv)>2 else H/'early_phase_native';out.mkdir(exist_ok=True,parents=True)
 before=par.read_text();after=inject(before);(out/'invsqrt.kmx').write_text(after);km.Circuit(after).to_file(str(out/'invsqrt.kmb'),format='kmb');F=lambda f:hashlib.sha256(f.read_bytes()).hexdigest();print('built',F(out/'invsqrt.kmb'),flush=True)
 k=sample(before,after);print('sample phases + cleanup',k,flush=True);(out/'certificate.json').write_text(json.dumps(dict(parent=F(par.with_suffix('.kmb')),child=F(out/'invsqrt.kmb'),exact_phase_and_cleanup_sample=k,relative_to='lazy_all_native'),indent=2)+'\n')
