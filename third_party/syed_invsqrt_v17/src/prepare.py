"""Bind legacy integrity manifests to the supplied source-only distribution.

Old native-release manifests also pinned historical comparison circuits, logs,
a Linux SDK binary, and research executables. None supplies generated gates.
All retained source files and their rebased integrity records remain checked.
"""
import hashlib
import json
import re
from pathlib import Path

DIGEST = re.compile(rb'(?<![\da-f])[a-f0-9]{64}(?![\da-f])')
SIMPLE_OBJECT = re.compile(rb'\{[^{}]{1,1200}\}')
SIZES = re.compile(rb'("bytes"\s*:\s*)\d+')
ROOT = Path('incumbent_sources/frozen_source/fusion/runtime')
OMIT_EXT = {'.bin','.cpp','.kmx','.kmb','.log','.so'}

def sha(data):
    return hashlib.sha256(data).hexdigest().encode()

def prepare(stage):
    runtime = stage / ROOT
    narrow = runtime / 'work/c10/narrow'
    original = {p:p.read_bytes() for p in stage.rglob('*') if p.is_file() and p.suffix in ('.py','.json')}
    direct = original.copy()
    changed, omissions = [], {}
    for p,data in original.items():
        if not p.is_relative_to(narrow):
            continue
        if p.name in ('INPUTS.json','SOURCE_READY.json'):
            cfg = json.loads(data)
            if not isinstance(cfg,dict) or not isinstance(cfg.get('files'),list):
                continue
            rows=cfg['files']
            keep=[]
            for q in rows:
                if not isinstance(q,dict) or 'path' not in q:
                    keep.append(q);continue
                name=Path(q['path'])
                # Only fixed archival binary, log, and comparison files may be skipped.
                if name.suffix in OMIT_EXT and not any((r/name).is_file() for r in [narrow,p.parent]):
                    omissions.setdefault(str(p.relative_to(stage)),[]).append(str(name))
                else:keep.append(q)
            if len(keep)!=len(rows):
                cfg['files']=keep;direct[p]=(json.dumps(cfg,indent=2)+'\n').encode()
        elif p == narrow/'research/postgate_angle_refit/quantize50.json':
            cfg=json.loads(data);pins=cfg['source_pins']
            drop=[q for q in pins if Path(q).suffix in OMIT_EXT and not (narrow/q).exists()]
            if drop:
                for q in drop:del pins[q]
                omissions[str(p.relative_to(stage))]=drop
                direct[p]=(json.dumps(cfg,indent=2)+'\n').encode()
        elif p in [narrow/'native/candidate01/common.py',narrow/'native/candidate01/tables.py']:
            lines=data.splitlines(keepends=True)
            kept=[s for s in lines if not (s.startswith(b'assert hashlib.sha256(') and b'kickmix.so' in s)]
            assert len(kept)==len(lines)-1,p
            direct[p]=b''.join(kept);changed.append(str(p.relative_to(stage)))
    content=direct.copy()
    for _ in range(64):
        rename={}
        for p,base in original.items():
            mod=content[p]
            if mod!=base:
                old=sha(base);value=(sha(mod),len(mod))
                if old in rename and rename[old]!=value:
                    raise ValueError(f'Ambiguous archived source identity for {p}')
                rename[old]=value
        def patch_object(m):
            part=m.group()
            if b'"bytes"' in part:
                for key in DIGEST.findall(part):
                    if key in rename:
                        part=SIZES.sub(lambda v:v.group(1)+str(rename[key][1]).encode(),part)
                        break
            return part
        nxt={}
        for p,base in direct.items():
            if b'"bytes"' in base:
                base=SIMPLE_OBJECT.sub(patch_object,base)
            nxt[p]=DIGEST.sub(lambda m:rename.get(m.group(),(m.group(),))[0],base)
        if nxt==content:break
        content=nxt
    else:raise ValueError('Unresolved cycle in archival source integrity records')
    for p,mod in content.items():
        if mod!=original[p]:p.write_bytes(mod)
    (stage/'source_adaptation.json').write_text(json.dumps(dict(omitted_comparisons=omissions,native_sdk_pin_removals=changed,source_rehashes=sum(content[p]!=original[p] for p in content)),indent=2)+'\n')
