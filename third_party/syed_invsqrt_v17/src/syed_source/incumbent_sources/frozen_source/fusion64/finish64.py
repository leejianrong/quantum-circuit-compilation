# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.
"""Conservative one-affine-pass finishing for changed lifecycle circuits; exact proof remains mandatory."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,sys
OWN=Path(__file__).resolve().parent
HERE=OWN.parent/"fusion"
FG=HERE/'runtime'

def update_new_phase_build(out,name,proof,report):
    """Replace the compiler's provisional frozen-margin cost with proof data."""
    report.update(status=proof['status'],cost_model=proof.get('cost_model'),
        phase_function='declared_new_integer_model',phase_parameters=proof['parameters'],
        phase_units50_sha256=proof['phase_units50_sha256'],accuracy=proof['accuracy'],
        proof_path=str(out/(name+'.proof.json')),
        proof_sha256=hashlib.sha256((out/(name+'.proof.json')).read_bytes()).hexdigest())
    (out/(name+'.build.json')).write_text(json.dumps(report,indent=2)+'\n')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('raw',type=Path);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--name',default='candidate');ap.add_argument('--Q',type=int,default=46)
    ap.add_argument('--canonical-after-divider',action='store_true')
    ap.add_argument('--native-tail',action='store_true')
    ap.add_argument('--new-phase-angles',type=Path)
    args=ap.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    (out/'FINISH_POLICY.json').write_text(json.dumps(dict(status='ONE_AFFINE_PASS_ONLY', source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), later_sampled_affine_passes_disabled=True, exact_full_domain_all_HMR_proof_still_required=True),indent=2)+'\n')
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
    def run(name,tool,*a):
        with (out/(name+'.log')).open('w') as log:
            subprocess.run([sys.executable,str(FG/'tools'/tool),*map(str,a)],env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
        print(name,'complete',flush=True)
    raw=args.raw.resolve()
    if args.canonical_after_divider:
        # The divider has returned all 31 data owners to their identical physical
        # roles and consumed every divider transcript. Restore the original
        # subsequent zero-wire allocation spelling, then prove the whole result.
        sys.path.insert(0,str(FG/'tools'))
        import kmsim
        baseline=FG/'runs/baseline_raw/t13raw.kmx'
        oldbuild=json.loads(baseline.with_suffix('.build.json').read_text())
        newbuild=json.loads(raw.with_suffix('.build.json').read_text())
        oldcut=next(c for c in oldbuild['cuts'] if c['name']=='divider_return')
        newcut=next(c for c in newbuild['cuts'] if c['name']=='divider_return')
        assert oldcut['owners']==newcut['owners'] and oldcut['live_qubits']==newcut['live_qubits']==31
        oldtext=baseline.read_text();newtext=raw.read_text()
        oldops,_=kmsim.parse(oldtext);newops,_=kmsim.parse(newtext)
        oldline=oldops[oldcut['instruction_cut']][4]-1
        newline=newops[newcut['instruction_cut']][4]-1
        joined='\n'.join(newtext.splitlines()[:newline]+oldtext.splitlines()[oldline:])+'\n'
        raw=out/'canonical_raw.kmx';raw.write_text(joined)
        (out/'suffix_splice.json').write_text(json.dumps({'old_cut':oldcut,'new_cut':newcut,'old_line':oldline+1,'new_line':newline+1,'requires_full_domain_all_HMR_proof':True},indent=2)+'\n')
    run('initial_affine','audit_affine.py',raw,'--out',out/'initial_affine.json')
    run('pairs','audit_pairs.py',raw,'--live',out/'initial_affine.live.npy','--out',out/'pairs.json')
    run('hold','hold_pass.py',raw,out/'pairs.json','--out',out/'held.kmx','--Q',args.Q)
    current=out/'held.kmx'
    for i in range(1):
        audit=out/f'affine{i}.json';run(f'affine{i}','audit_affine.py',current,'--out',audit)
        findings=json.loads(audit.read_text())['findings']
        if not findings:break
        nxt=out/f'pass{i}.kmx';run(f'pass{i}','postpass.py',current,audit,'--out',nxt);current=nxt
    run('zpow','merge_zpow.py',current,'--out',out/'zpow.kmx')
    run('relocate','tk/relocate_cs2.py',out/'zpow.kmx',out/'t13.kmx')
    if args.native_tail:
        (out/'final_text.kmx').write_text((out/'t13.kmx').read_text())
    else:
        old=(FG/'runs/t13/final/final_text.kmx').read_text().splitlines()
        new=(HERE.parents[1]/'pkg/fusion/t17/t17.kmx').read_text().splitlines()
        p=0
        while p<min(len(old),len(new)) and old[p]==new[p]:p+=1
        s=0
        while s<min(len(old),len(new))-p and old[-s-1]==new[-s-1]:s+=1
        before='\n'.join(old[p:len(old)-s]);after='\n'.join(new[p:len(new)-s])
        text=(out/'t13.kmx').read_text()
        assert text.count(before)==1, ('T17 decoder transplant not unique or changed',text.count(before),p,s)
        text=text.replace(before,after)
        (out/'final_text.kmx').write_text(text)
        (out/'decoder_transplant.json').write_text(json.dumps({'baseline_first_changed_line':p+1,'baseline_suffix_lines':s,'before_sha256':hashlib.sha256(before.encode()).hexdigest(),'after_sha256':hashlib.sha256(after.encode()).hexdigest(),'exact_occurrences':1},indent=2))
    run('compile','kmx_to_kmb.py',out/'final_text.kmx','--out',out/(args.name+'.kmb'))
    report=json.loads((out/(args.name+'.build.json')).read_text())
    print(json.dumps({'status':'MECHANICALLY_FINISHED_AWAITING64_ROW_PROOF','Q':report['Q'],'kmb_sha256':report['kmb_sha256'],'resources':report.get('exact_native_expectation',report.get('expectation'))}),flush=True)
if __name__=='__main__':main()
