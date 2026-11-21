# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Root full-domain/all-HMR occupancy for a bound, fully proved native candidate."""
from pathlib import Path
from collections import Counter
import argparse,gzip,json,time
import numpy as np
from map_incumbent_width import BASE,NOTICE,Program,px,pm,runs,sha

def occupancy(native):
    program=Program(native.read_text());n=3133452;full=(1<<n)-1;one={0:full}
    xs=np.arange(1,n+1,dtype=np.uint64)
    state={q:{} for q in program.wires};state.update({'0':{},'False':{},'1':one,'True':one})
    initial={}
    for bit,q in enumerate(program.registers['x']):
        v=int.from_bytes(np.packbits(((xs>>bit)&1).astype(np.uint8),bitorder='little').tobytes(),'little')
        state[q]=initial[q]={0:v}
    del xs
    stack=[one];quantum=list(program.quantum_wires);masks=[]
    def record():masks.append(sum(bool(state[q])<<int(q[1:]) for q in quantum))
    record()
    for i,op in enumerate(program.operations):
        k,a=op.kind,op.arguments
        if k=='PUSH_CONDITION':stack.append(stack[-1] if op.condition is None else pm(stack[-1],state[op.condition]))
        elif k=='POP_CONDITION':assert len(stack)>1;stack.pop()
        elif k not in ('Z','CZ','CCZ','NEG','Z_POW'):
            g=stack[-1] if op.condition is None else pm(stack[-1],state[op.condition])
            if g:
                if k in ('X','BIT_INVERT'):state[a[0]]=px(state[a[0]],g)
                elif k=='CX':state[a[1]]=px(state[a[1]],pm(g,state[a[0]]))
                elif k=='CCX':state[a[2]]=px(state[a[2]],pm(g,pm(state[a[0]],state[a[1]])))
                elif k in ('SWAP','CSWAP'):
                    u,v=a[-2:];d=pm(g,px(state[u],state[v]))
                    if k=='CSWAP':d=pm(d,state[a[0]])
                    state[u],state[v]=px(state[u],d),px(state[v],d)
                elif k=='HMR':
                    c=px(one,g);state[a[0]]=pm(c,state[a[0]])
                    state[a[1]]=px(pm(c,state[a[1]]),pm(g,{1<<op.event:full}))
                elif k in ('BIT_STORE0','BIT_STORE1'):
                    v=one if k=='BIT_STORE1' else {};state[a[0]]=px(state[a[0]],pm(g,px(state[a[0]],v)))
                elif k=='R':assert not pm(g,state[a[0]])
                else:raise AssertionError((i,k))
        record()
    assert stack==[one] and all(state[q]==v for q,v in initial.items())
    assert all(not state[q] for q in quantum if q not in initial)
    return program,masks

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--native',required=True,type=Path);ap.add_argument('--proof-dir',required=True,type=Path);ap.add_argument('--out',required=True,type=Path);ap.add_argument('--interval',nargs=3,action='append',default=[]);args=ap.parse_args();began=time.monotonic()
    assert not args.out.exists();args.out.mkdir(parents=True)
    proof=json.loads((args.proof_dir/'proof.json').read_text());rp=json.loads((args.proof_dir/'ROOT_PROOF_RECEIPT.json').read_text())
    assert rp['source_native_sha256']==sha(args.native) and rp['circuit_sha256']==sha(args.proof_dir/'candidate.kmb')
    assert proof['qualified'] and proof['proved_inputs']==3133452 and proof['every_HMR_transcript_proved']
    program,masks=occupancy(args.native);hist=Counter(m.bit_count() for m in masks);intervals=[]
    for name,a,b in args.interval:
        a,b=int(a),int(b);h=Counter(m.bit_count() for m in masks[a:b+1]);assert max(h)<=43
        intervals.append(dict(name=name,closed_cut_interval=[a,b],peak=max(h),histogram=dict(sorted(h.items())),peak44_cuts=0))
    maskpath=args.out/'ALL_INPUT_ALL_HMR_OCCUPANCY.json.gz'
    maskpath.write_bytes(gzip.compress((json.dumps(dict(notice=NOTICE,native_sha256=sha(args.native),masks=masks),separators=(',',':'))+'\n').encode(),mtime=0))
    report=dict(notice=NOTICE,status='ROOT_FULL_DOMAIN_PROOF_BOUND_VALUE_OCCUPANCY_AUDIT_PASS',native_sha256=sha(args.native),circuit_sha256=sha(args.proof_dir/'candidate.kmb'),proof_sha256=sha(args.proof_dir/'proof.json'),Q=proof['Q'],expected_Toffolis=proof['exact_native_expectation']['mean']['toffoli_like'],full_original_inputs=3133452,every_HMR_branch=True,operations=len(program.operations),HMR=program.measurements,global_peak=max(hist),global_histogram=dict(sorted(hist.items())),peak44_windows=runs(masks,lambda m:m.bit_count()==44),peak44_cuts=hist.get(44,0),proved_local_intervals=intervals,global_Q43_not_yet_claimed=True,bindings={str(p.resolve().relative_to(BASE)):sha(p) for p in [Path(__file__),args.native,args.proof_dir/'ROOT_PROOF_RECEIPT.json',args.proof_dir/'proof.json',maskpath]},seconds=time.monotonic()-began)
    (args.out/'REPORT.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ('global_histogram','peak44_windows','bindings')},indent=2))
if __name__=='__main__':main()
