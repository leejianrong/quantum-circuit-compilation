"""On the native Q43 branch, combine two masked old-target cubic phases on the same paid product."""
import hashlib,itertools,json,sys
from pathlib import Path
import numpy as np,kickmix as km
H=Path(__file__).resolve().parent;P=H.parent/'phase_agent/invsqrt.kmx'
L1=(8,15,30,34);L2=(7,16,18,29,30,34)
def cut(lines):
 before='PUSH_CONDITION if b361\nPUSH_CONDITION if b366\nCX q15 q8\nCX q30 q8\nCX q34 q8\nCX q36 q8\nCCZ q17 q0 q8\n'
 replaced='PUSH_CONDITION if b361\nBIT_INVERT b366 if b367\nCCZ q17 q0 q36 if b366\nBIT_INVERT b366 if b367\nPUSH_CONDITION if b366\nCX q15 q8\nCX q30 q8\nCX q34 q8\nCX q36 q8\n'
 mid='CX q16 q7\nCX q18 q7\nCX q29 q7\nCX q30 q7\nCX q34 q7\nCX q36 q7\nCCZ q17 q0 q7\n'
 end='HMR q36 b984\nPUSH_CONDITION if b361\nCX q17 q36\nCX q7 q36\nCX q18 q36\nCX q21 q36\nCCX q17 q0 q36\n'
 for key in [before,mid,end]:assert lines.count(key)==1,key
 rep=''.join(f'CZ q36 q{x} if b{k}\n' for k,L in [(366,L1),(367,L2)] for x in L)
 return lines.replace(before,replaced).replace(mid,mid.removesuffix('CCZ q17 q0 q7\n')).replace(end,end.removesuffix('CCX q17 q0 q36\n')+rep+'CCX q17 q0 q36\n'+rep)
def check():
 for a,b,w,L1,L2,pre,g,c,d in itertools.product(range(2),repeat=9):
    old=g*a*b*((c*(L1^w))^(d*(L2^w)))
    new=g*((c^d)*a*b*w ^ ((c*L1)^(d*L2))*(pre^(pre^(a*b))))
    assert old==new
 return 512
def sample(parent,child):
 xs=np.random.default_rng(99310).integers(1,3133453,24576,dtype=np.uint64);xs[:1024]=np.arange(1,1025)
 ini=((xs[None,:]>>np.arange(22,dtype=np.uint64)[:,None])&1).astype(bool)
 results=[]
 for lines in (parent,child):
    s=km.Simulator(len(xs),seed=565741);s.write_across_shots([km.q(i) for i in range(22)],ini);s.do(km.Circuit(lines))
    state=s.read_across_shots([km.q(i) for i in range(43)]);results.append((state,[s.read_shot_phase(shot_index=i) for i in range(len(xs))]))
 assert np.array_equal(results[0][0],results[1][0]);assert np.array_equal(results[0][1],results[1][1])
 return len(xs)
if __name__=='__main__':
 par=Path(sys.argv[1]) if len(sys.argv)>1 else P;out=Path(sys.argv[2]) if len(sys.argv)>2 else H/'overlap_native';out.mkdir(exist_ok=True,parents=True)
 src=par.read_text();dst=cut(src);truth=check();(out/'invsqrt.kmx').write_text(dst);c=km.Circuit(dst);c.to_file(str(out/'invsqrt.kmb'),format='kmb');F=lambda x:hashlib.sha256(x.read_bytes()).hexdigest()
 h=F(out/'invsqrt.kmb');parent=F(par.with_suffix('.kmb'));print('built',h,'parent',parent,truth,flush=True)
 s=sample(src,dst);(out/'certificate.json').write_text(json.dumps(dict(parent=parent,child=h,truth_table=truth,phase_and_cleanup_sample=s),indent=2)+'\n');print('phase + cleanup sample',s)
