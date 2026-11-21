# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Replay a fixed late43-owner plan and verify a universal exact ANF identity."""
from pathlib import Path
import argparse,json,time
from map_incumbent_width import BASE,NOTICE,Program,sha
from explore_q43_late_virtual_owner import pm
PARENT_SHA='23f2ecd3f88f4b72d7657abae0027511d64ec0201d4985e004608e15b11144c3'

def replay(operations):
    state={f'q{i}':frozenset([1<<i]) for i in range(44)};state['q21']=frozenset()
    phase=frozenset();event=44;cost=0
    for op in operations:
        k,a=op.kind,op.arguments;assert op.condition is None
        if k=='X':state[a[0]]^={0}
        elif k=='CX':state[a[1]]^=state[a[0]]
        elif k=='CCX':state[a[2]]^=pm(state[a[0]],state[a[1]]);cost+=1
        elif k=='SWAP':state[a[0]],state[a[1]]=state[a[1]],state[a[0]]
        elif k=='HMR':
            assert event==44;state[a[1]]=frozenset([1<<event]);phase^=pm(state[a[0]],state[a[1]])
            state[a[0]]=frozenset();event+=1
        else:raise AssertionError((k,a))
    assert event==45
    return state,phase,cost

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--native',type=Path,default=BASE/'agents/temporal_merges/q43_integrated_width_base_v1/candidate_text.kmx');ap.add_argument('--out',type=Path,required=True);args=ap.parse_args();began=time.monotonic()
    assert sha(args.native)==PARENT_SHA and not args.out.exists()
    planpath=BASE/'root/q43_late_virtual_owner_v1/REPORT.json';plan=json.loads(planpath.read_text());a,b=plan['parent_interval']
    assert(a,b)==(31119,31390) and plan['modelled_block_ANDs']==2
    text=args.native.read_text();p=Program(text);changed_block=Program('\n'.join(plan['gates'])+'\n')
    before=replay(p.operations[a:b]);after=replay(changed_block.operations)
    assert before[0]==after[0] and before[1]==after[1] and before[2]==1 and after[2]==2
    lines=text.splitlines();oplines=[i for i,line in enumerate(lines) if line.strip() and not line.strip().startswith(('#','INFO_TAG','DEBUG_PRINT','APPEND_TO_REGISTER','REGISTER'))]
    assert len(oplines)==len(p.operations)
    changed='\n'.join(['# '+NOTICE]+lines[:oplines[a]]+plan['gates']+lines[oplines[b]:])+'\n'
    args.out.mkdir(parents=True);dest=args.out/'candidate_text.kmx';dest.write_text(changed)
    assert sha(dest)==plan['candidate_native_sha256']=='e9459050b85e6a2fa783d38251383c1212d859d9b8fa358c8eee245d21f03a01'
    report=dict(notice=NOTICE,status='ROOT_UNIVERSAL_43_INDEPENDENT_INPUT_BITS_AND_HMR_POLYNOMIAL_IDENTITY_PASS',native_sha256=sha(dest),parent_native_sha256=PARENT_SHA,initial_precondition='q21=0; all other43 quantum owners arbitrary independent formal bits',formal_quantum_inputs=43,formal_HMR_outcomes=1,all44_outputs_equal=True,classical_outcome_identical=True,binary_phase_equal=True,rotations_in_window=0,original_ANDs=1,new_ANDs=2,added_expected_Toffolis='1',unchanged_HMR_owner_value=True,maximum_output_ANF_terms=max(len(v) for v in after[0].values()),bindings={str(x.resolve().relative_to(BASE)):sha(x) for x in [Path(__file__),BASE/'root/explore_q43_late_virtual_owner.py',planpath,args.native,dest]},seconds=time.monotonic()-began)
    (args.out/'REBUILD_AND_FORMAL_IDENTITY.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
