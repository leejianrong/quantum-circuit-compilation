"""Reapply the owner's verified measurement, normalization and coefficient cuts to F16+."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import kickmix as km

from coefficient_windows import first_window, second_window
from normalizer import optimize as normalize
from return_shift import optimize as unnormalize
from target_phase import cut as target_payment


def optimize(parent_text, out):
    src=Path(__file__).resolve().parent/'lineage/hand_cuts'
    sys.path.insert(0,str(src))
    from early_phase import inject as use_early_product
    from retire170 import cut_shared
    from retire171 import cut_shared_171
    from clifford_retire import cut_clifford

    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    # The coefficient passes address rows of the parent's first majority-cut circuit.
    majority=target_payment(parent_text)
    original=majority.splitlines()
    steps=[('majority',lambda _:majority,'7a4e3d7b'),('early_product',use_early_product,'4baa7e25'),
           ('normalize',normalize,'85657ba0'),('unnormalize',unnormalize,'1a7ac49c'),
           ('retire170',lambda text:cut_shared(text,both=True),'f13a150c'),
           ('retire171',cut_shared_171,'715906f9'),('clifford',cut_clifford,'39eb4fc0'),
           ('first_coefficient',lambda text:'\n'.join(first_window(text.splitlines(),original))+'\n','3391f534'),
           ('second_coefficient',lambda text:'\n'.join(second_window(text.splitlines(),original))+'\n','70fe5f79')]
    text=parent_text;hashes={}
    for stage,fn,reference in steps:
        text=fn(text);member=out/(stage+'.kmb')
        km.Circuit(text).to_file(str(member),format='kmb')
        h=hashlib.sha256(member.read_bytes()).hexdigest();hashes[stage]=h
        print(stage,h,flush=True)
        if not h.startswith(reference):
            (out/(stage+'.kmx')).write_text(text)
            raise ValueError(f'{stage}: expected {reference}, computed {h}')
    (out/'cuts.json').write_text(json.dumps(hashes,indent=2)+'\n')
    return text


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('parent',type=Path);p.add_argument('out',type=Path)
    args=p.parse_args();text=optimize(args.parent.read_text(),args.out)
    (args.out/'invsqrt.kmx').write_text(text);km.Circuit(text).to_file(str(args.out/'invsqrt.kmb'),format='kmb')
