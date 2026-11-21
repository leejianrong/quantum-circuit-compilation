"""Retire a leased q31 via its native HMR when both later uses are disabled; restore on demand elsewhere."""
from leased_more import *
from leased_more import inject as prior

def restore31(early):
 gates=['CX q11 q31','CX q13 q31','CX q20 q31','CX q10 q12','CX q10 q20']
 if early:gates+=['CX q34 q20']
 gates+=['CCX q12 q20 q31']
 if early:gates+=['CX q34 q20']
 return gates+['CX q10 q20','CX q10 q12']

def inject(src):
 s=prior(src)
 old=['Z q10 if b15010','Z q13 if b15010','Z q20 if b15010','Z q31 if b15010','CZ q10 q12 if b15010','CZ q10 q20 if b15010','CZ q10 q34 if b15010','CZ q12 q20 if b15010','CZ q12 q34 if b15010']
 new=[x.replace('Z q31 if','Z q11 if') for x in old]
 z='\n'.join(['HMR q11 b15010']+old)+'\n';xp='\n'.join(['HMR q31 b15010']+new)+'\n';assert s.count(z)==2;s=s.replace(z,xp)
 # Only our own helper-target gates are renamed. The physical source q11 is still live in the reconstruction.
 for qin,tail in [('CX q16 q11','CZ q21 q17 if b15011'),('CX q21 q11','CZ q21 q7 if b15011')]:
    start=s.index(qin+'\n',s.index(xp));end=s.index(tail+'\n',start)+len(tail);chunk=s[start:end];s=s[:start]+chunk.replace('q11','q31')+s[end:]
 for line in ['CCX q17 q0 q11 if b15012','CZ q11 q8 if b15012','CZ q11 q7 if b15012','CX q11 q36 if b15012']:
    assert s.count(line)==1;s=s.replace(line,line.replace('q11','q31'))
 start=s.index('HMR q11 b15013');end=s.index('POP_CONDITION\n',start);s=s[:start]+'HMR q31 b15013\nCZ q17 q0 if b15013\n'+s[end:]
 tag='HMR q26 b193\nPUSH_CONDITION if b361\nPUSH_CONDITION if b193\nX q31\n';assert s.count(tag)==1
 a='HMR q26 b193\nBIT_STORE0 b15014\nBIT_STORE1 b15014 if b15012\nBIT_STORE0 b15014 if b193\nPUSH_CONDITION if b361\nPUSH_CONDITION if b193\nPUSH_CONDITION if b15012\n'+'\n'.join(restore31(True))+'\nPOP_CONDITION\nX q31\n';s=s.replace(tag,a)
 tag='BIT_INVERT b361\nX q27\nCX q34 q27\nX q9\nCX q34 q9\nX q20\nCX q34 q20\nX q31\nCX q34 q31\nX q33\nCX q34 q33\n';assert s.count(tag)==1
 s=s.replace(tag,tag.replace('CX q34 q31\n','BIT_INVERT b15014\nCX q34 q31 if b15014\nBIT_INVERT b15014\n'))
 tag='HMR q33 b360\nPUSH_CONDITION if b360\nZ q11\nZ q12\nZ q14\nZ q31\n';assert s.count(tag)==1
 z='HMR q33 b360\nBIT_STORE0 b15015\nBIT_STORE1 b15015 if b15014\nBIT_STORE0 b15015 if b360\nPUSH_CONDITION if b360\nPUSH_CONDITION if b15014\n'+'\n'.join(restore31(False))+'\nPOP_CONDITION\nZ q11\nZ q12\nZ q14\nZ q31\n';s=s.replace(tag,z)
 tag='HMR q31 b360\nPUSH_CONDITION if b360\nZ q10\nZ q11\nZ q13\n';assert s.count(tag)==1;s=s.replace(tag,tag.replace('PUSH_CONDITION','BIT_STORE0 b360 if b15015\nPUSH_CONDITION'))
 return s
if __name__=='__main__':
 par=pathlib.Path(sys.argv[1]) if len(sys.argv)>1 else P;out=pathlib.Path(sys.argv[2]) if len(sys.argv)>2 else H/'lazy_native';out.mkdir(exist_ok=True,parents=True)
 before=par.read_text();after=inject(before);(out/'invsqrt.kmx').write_text(after);km.Circuit(after).to_file(str(out/'invsqrt.kmb'),format='kmb');F=lambda f:hashlib.sha256(f.read_bytes()).hexdigest();print('built',F(out/'invsqrt.kmb'),flush=True)
 k=sample(before,after);print('sample phases + cleanup',k,flush=True);(out/'certificate.json').write_text(json.dumps(dict(parent=F(par.with_suffix('.kmb')),child=F(out/'invsqrt.kmb'),exact_phase_and_cleanup_sample=k,relative_to='leased_more_native'),indent=2)+'\n')
