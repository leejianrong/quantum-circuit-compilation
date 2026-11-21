"""Replay the owner's Stack-4 and F16+ compiler passes on the generated arithmetic."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import kickmix as km

from phase_fit import port


ASSETS=Path(__file__).resolve().parent/'lineage'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_windows(lines, specs, shift=0):
    for item in sorted(specs,key=lambda row:-row['begin']):
        lo,hi=item['begin']+shift,item['end']+shift
        old='\n'.join(lines[lo:hi])
        if hashlib.sha256(old.encode()).hexdigest()!=item['original_window_sha256']:
            raise ValueError(f"original window {item['id']} differs from its checked source")
        lines[lo:hi]=item['instructions']
    return lines


def build(origin, original_fit, out):
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    expected=json.loads((ASSETS/'expected.json').read_text()); measured={}
    def check(name,member):
        actual=sha(member)
        if actual!=expected[name]:
            raise ValueError(f'{name} hash differs: {actual} versus {expected[name]}')
        measured[name]=actual
        print(name,actual,flush=True)
    def emit(name,lines):
        dest=out/name;dest.mkdir(exist_ok=True)
        text=lines if isinstance(lines,str) else '\n'.join(lines)+'\n'
        fp=dest/'candidate.kmx';fp.write_text(text);km.Circuit(text).to_file(str(dest/'invsqrt.kmb'),format='kmb')
        check(name,dest/'invsqrt.kmb');return fp
    def run(stage,script,args,extra=None):
        path=out/(stage+'-'+Path(script).stem+'.log')
        with path.open('w') as log:
            result=subprocess.run([sys.executable,'-B',str(ASSETS/stage/script),*map(str,args)],cwd=out,
                       env={**os.environ,**(extra or {})},stdout=log,stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError(path.read_text()[-2500:])
    def pkg(stage,file):
        return ASSETS/stage/file
    def build_stage(stage,parent,script,inputs):
        dest=out/stage
        run(stage,'sources/'+script,[parent,*[pkg(stage,x) for x in inputs],dest]);check(stage,dest/'invsqrt.kmb')
        return dest/'candidate.kmx'
    original=str(km.Circuit.from_file(str(origin)))
    base=[line.strip() for line in original.splitlines() if line.strip() and not line.lstrip().startswith('#')]
    cfg=json.loads((ASSETS/'windows.json').read_text());wins=cfg['windows']
    two=replace_windows(base.copy(),wins[:2]);emit('Stack2',two)
    hit=cfg['parity'];ws=hit['v_wires'];pivot=ws[0]
    assert not hit['v_const'] and two[hit['ccz']]==hit['ccz_line']
    prep=[f'CX q{x} q{pivot}' for x in ws[1:]]
    payment=prep+[f'CZ q{hit["holder"]} q{pivot}']+prep[::-1]
    three=[]
    for k,op in enumerate(two):
        if k in (hit['at'],hit['at_after']):three.extend(payment)
        if k!=hit['ccz']:three.append(op)
    emit('Stack3',three)
    four=replace_windows(three.copy(),wins[2:],len(three)-len(base));emit('Stack4',four)
    old=json.loads(Path(original_fit).read_text());gauge=json.loads(pkg('F01','sources/gauge_fit.json').read_text())
    tuned=port('\n'.join(four)+'\n',old,gauge)
    stack=emit('Stack4Gauge',tuned)
    f01=build_stage('F01',stack,'build_angles.py',['sources/gauge_fit.json','fit.json'])
    f02=build_stage('F02',f01,'build_temporal.py',['sources/edits.json'])
    f03=build_stage('F03',f02,'build_handoff.py',['sources/edits.json'])
    f04=build_stage('F04',f03,'build_fine.py',['sources/parent_fit.json','fit.json'])
    f12=out/'F12';intermediate=f12/'ring'
    run('F12','sources/build_encoded_walk.py',[f04,pkg('F12','fit.json'),pkg('F12','sources/plan.json'),pkg('F12','sources/word.json'),intermediate])
    run('F12','sources/build_delayed_product.py',[intermediate/'candidate.kmx',pkg('F12','sources/selected_repair.json'),f12]);check('F12',f12/'invsqrt.kmb')
    f13=build_stage('F13',f12/'candidate.kmx','build_relocated.py',['sources/parent_fit.json','fit.json'])
    f15=build_stage('F15',f13,'build_joint_cubic.py',['sources/selected.json'])
    f16=out/'F16';f16.mkdir(exist_ok=True)
    run('F16','f16_build.py',[f16/'candidate.kmx','--last','--trans'],{'F15_KMX':str(f15)})
    km.Circuit.from_file(str(f16/'candidate.kmx')).to_file(str(f16/'invsqrt.kmb'),format='kmb');check('F16',f16/'invsqrt.kmb')
    plus=out/'F16plus';(plus/'results').mkdir(parents=True,exist_ok=True)
    run('F16plus','build_f16_plus_v1.py',[f16/'invsqrt.kmb',plus]);final=plus/'results/invsqrt_f16_plus_v1.kmb';check('F16plus',final)
    (out/'lineage.json').write_text(json.dumps(measured,indent=2)+'\n')
    return final


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('origin',type=Path);p.add_argument('original_fit',type=Path);p.add_argument('out',type=Path)
    args=p.parse_args();build(args.origin,args.original_fit,args.out)
