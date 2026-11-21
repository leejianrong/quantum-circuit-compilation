"""Build Syed Asad Ali's inverse-square-root compiler using only source and numeric witnesses."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile

HERE=Path(__file__).resolve().parent
RT=Path('incumbent_sources/frozen_source/fusion/runtime')
def digest(p):
    with p.open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def build(out):
    import kickmix as km
    out.mkdir(exist_ok=True,parents=True);work=out/'stages';work.mkdir()
    assert digest(HERE/'syed_source.zip')=='1c3d7d7b66ad4df27ad216d03c3b77a095554580e84e5363b366f4512b7d241d'
    with zipfile.ZipFile(HERE/'syed_source.zip')as z:z.extractall(work)
    runtime=work/RT;dag=json.loads((work/'dag.json').read_text());release=json.loads((work/'original.json').read_text())
    macro=next(work.rglob('*.kmx.macro'));macro.rename(macro.with_suffix(''))
    # Only the path binding changes. The source's historical on-disk layout was platform-specific.
    old='/workspace/scratch/394c5ff892d3/recovered/candidate32/research/fusion/runtime'
    for file in work.rglob('*.py'):
        source=file.read_text();new=source.replace(old,str(runtime)).replace('/Users/asad.ali/codex quantum/fusion3_reduced_anchor/reference_build/'+str(RT),str(runtime))
        if source!=new:file.write_text(new)
    from prepare import prepare
    prepare(work)
    logs=work/'logs';logs.mkdir();env=os.environ.copy()
    for key in ('FUSION_SOURCE_PROJECT','FUSION_SOURCE_RUNTIME'):
        env.pop(key,None)
    temp=work/'temp';temp.mkdir();env.update(TMPDIR=str(temp),XDG_CACHE_HOME=str(temp/'cache'),MPLCONFIGDIR=str(temp/'matplotlib'))
    env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1',NUMBA_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
    engine=runtime/'work/c10/narrow/checkpoint002/cleanroom/baseline_stage97'
    env['SYED_SOURCE_ROOT']=str(work)
    paths=[HERE,engine/'engine',engine/'tests',work/'restored/research_v9/second_seed_and_phases',Path(km.__file__).resolve().parent]
    env['PYTHONPATH']=os.pathsep.join(map(str,paths))
    native_paths={}
    def run(name,cmd,cwd,extra=None):
        print(name,flush=True);fp=logs/(name+'.log')
        with fp.open('w')as f:
            r=subprocess.run(cmd,cwd=cwd,env={**env,**(extra or {})},stdout=f,stderr=subprocess.STDOUT)
        if r.returncode:raise RuntimeError(name+' failed\n'+fp.read_text()[-4000:])
    for j,stage in enumerate(dag['stages']):
        name=stage['id'];dst=work/f'_build/{j:02}_{name}'
        def subst(v):return v.replace('{ROOT}',str(work)).replace('{OUT}',str(dst)).replace('{PYTHON}',sys.executable)
        cwd=Path(subst(stage['cwd']));cwd.mkdir(exist_ok=True,parents=True)
        run(name,[subst(o)for o in stage['argv']],cwd,{k:subst(v)for k,v in stage['environment'].items()})
        for row in stage['exports']:
            made=dst/row['generated'];assert digest(made)==row['expected_sha256'],(name,made,digest(made))
            to=work/row['destination'];to.parent.mkdir(exist_ok=True,parents=True);assert not to.exists();shutil.copyfile(made,to);native_paths[name]=digest(to)
    logical=work/'logical';packed=work/'physical'
    run('metadata',[sys.executable,'-B',str(work/release['metadata_emitter']),'--out',str(logical),'--build-only'],work)
    run('packing',[sys.executable,'-B',str(work/'root/pack_actual_q43_native.py'),'--native',str(logical/'candidate_text.kmx'),'--out',str(packed),'--expected-native-sha256',release['logical_native_sha256']],work)
    assert digest(packed/'candidate_text.kmx')==release['physical_native_sha256']
    circuit=km.Circuit.from_file(str(packed/'candidate_text.kmx'),format='kmx');circuit.to_file(str(work/'original.kmb'),format='kmb')
    assert digest(work/'original.kmb')==release['circuit_sha256']
    from owner_lineage import build as rebuild_f16
    from finish_f16 import optimize
    lineage_dir=out/'lineage_stages'
    cuts_dir=out/'verified_cuts'
    parent=rebuild_f16(work/'original.kmb',work/'incumbent_sources/frozen_source/fusion64/native_angles.json',lineage_dir)
    fitted=optimize(parent.with_suffix('.kmx').read_text(),cuts_dir)
    km.Circuit(fitted).to_file(str(out/'invsqrt.kmb'),format='kmb')
    final=digest(out/'invsqrt.kmb')
    assert final=='70fe5f79d56bd48cd8fc9602757a0520b4d11859967627906cccb3dec25b7692',final
    receipt={'parent':release['circuit_sha256'],'stage_hashes':native_paths,
             'lineage':json.loads((lineage_dir/'lineage.json').read_text()),
             'cuts':json.loads((cuts_dir/'cuts.json').read_text()),'sha256':final}
    (out/'build_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);build(p.parse_args().out.resolve())
