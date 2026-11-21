"""Retire the early dirty-target product at the later native divider product."""
from overlap import H, sample, km
import argparse
import hashlib
import json
from pathlib import Path


def cut_shared(source, both=False):
    old = 'POP_CONDITION\nCZ q16 q7\nCCX q30 q8 q16\nCZ q16 q7\nCX q21 q16\n'
    tag = 'CX q29 q7\nCX q21 q30\nCX q34 q21\nCCX q21 q30 q7\nCX q34 q7\n'
    assert source.count(old) == source.count(tag) == 1
    assert 'b15021' not in source and 'b15022' not in source
    origin = ['BIT_STORE1 b15021']
    if both:
        origin.append('BIT_STORE1 b15022 if b13041')
    else:
        origin += ['BIT_STORE0 b15021 if b13041', 'CCX q30 q8 q16 if b13041']
    source = source.replace(old, old.replace('CCX q30 q8 q16', '\n'.join(origin)))
    side = ['CX q7 q16', 'CZ q7 q15', 'CZ q7 q34', 'CZ q7 q36']
    once = ['CX q21 q16', 'Z q21', 'CZ q21 q30', 'CZ q21 q15', 'CZ q21 q34', 'CZ q21 q36']
    new = ['PUSH_CONDITION if b15021', *once, *side, 'POP_CONDITION']
    if both:
        new += ['PUSH_CONDITION if b15022','CZ q21 q7','Z_POW q21 1.75','Z_POW q30 1.75','CX q21 q30','Z_POW q30 0.25','CX q21 q30','Z_POW q7 1.5','POP_CONDITION']
    new += ['CCX q21 q30 q7']
    if both:
        new += ['Z_POW q7 0.5 if b15022']
    new += ['PUSH_CONDITION if b15021', *side, 'POP_CONDITION']
    return source.replace(tag, tag.replace('CCX q21 q30 q7', '\n'.join(new)))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('input', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--both', action='store_true')
    a = p.parse_args()
    src = a.input.read_text()
    dst = cut_shared(src, a.both)
    a.output.mkdir(parents=True, exist_ok=True)
    (a.output/'invsqrt.kmx').write_text(dst)
    km.Circuit(dst).to_file(str(a.output/'invsqrt.kmb'), format='kmb')
    digest = lambda f: hashlib.sha256(f.read_bytes()).hexdigest()
    child = digest(a.output/'invsqrt.kmb')
    print('built',child,flush=True)
    n = sample(src,dst)
    print('sample',n,flush=True)
    (a.output/'certificate.json').write_text(json.dumps(dict(parent=digest(a.input.with_suffix('.kmb')),child=child,both=a.both,shots=n),indent=2)+'\n')
