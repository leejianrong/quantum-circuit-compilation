# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0. Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.
"""Compile disjoint joint measurement branches into native Clifford corrections and a shared cubic."""
import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

import kickmix

from build_angles import NOTICE
from build_walk import xor_sequence

sys.path.insert(0,str(Path(__file__).resolve().parent/'own'))
from kmscan import parse_kmx


def multiply(first, second):
    result=set()
    for a in first:
        for b in second:
            result.symmetric_difference_update([tuple(sorted(set(a)|set(b)))])
    return sorted(result)


def cubic_frame(forms, bit):
    wires=sorted({j for m in forms for j in range(43) if m>>j&1})
    parity=[sum(((m>>w)&1)<<j for j,w in enumerate(wires)) for m in forms]
    piv={};rows=[]
    for base in [*parity,*[1<<j for j in range(len(wires))]]:
        v=base
        while v and v.bit_length() in piv:v^=piv[v.bit_length()]
        if v:
            piv[v.bit_length()]=v;rows.append(base)
    assert rows[:3]==parity and len(rows)==len(wires)
    order=xor_sequence(wires,rows)
    flip=[f'X q{w}' for w,m in zip(wires,forms) if m>>43]
    gate='CCZ '+' '.join(f'q{w}'for w in wires[:3])
    # The linear map is computed and undone within the same original classical frame.
    return [*order,*flip,gate+f' if b{bit}',*flip[::-1],*order[::-1]]


def main():
    p=argparse.ArgumentParser()
    for k in ('parent','spec','out'):p.add_argument(k,type=Path)
    a=p.parse_args();plan=json.loads(a.spec.read_text())
    assert hashlib.sha256(a.parent.read_bytes()).hexdigest()==plan['parent_sha256']
    ops=parse_kmx(a.parent);base=kickmix.Circuit(a.parent.read_text());nb=base.num_bits
    before=defaultdict(list);after=defaultdict(list);actions=defaultdict(list)
    stored={};joints=defaultdict(list);joint_anf={};depth=[];level=0
    for o in ops:
        depth.append(level)
        level+=int(o.name=='PUSH_CONDITION')-int(o.name=='POP_CONDITION')
    assert not level
    for h in plan['rewrites']:
        i,j=h['sites'];assert ops[i].name==ops[j].name=='CCZ'
        anf=multiply(*h['guards']);assert anf
        birth=max(w for mon in anf for w in mon)+1
        while depth[birth]:birth+=1
        assert birth<=min([i,j,*[pos for pos,terms in h['terms']]])
        bit=nb;nb+=1;joint_anf[bit]=anf
        for mono in anf:
            for atom in mono:
                if atom in stored:continue
                o=ops[atom];assert o.name=='HMR'
                alias=nb;nb+=1;stored[atom]=alias
                if o.cond is not None:after[atom].append(f'PUSH_CONDITION if b{o.cond}')
                after[atom].append(f'BIT_INVERT b{alias} if b{o.bs[0]}')
                if o.cond is not None:after[atom].append('POP_CONDITION')
            before[birth]+=([f'PUSH_CONDITION if b{stored[w]}' for w in mono]+[f'BIT_INVERT b{bit}']+['POP_CONDITION']*len(mono))
        joints[i].append(bit);joints[j].append(bit)
        for pos,ws in h['terms']:
            assert pos in (i,j) or depth[pos]==0
            actions[pos].append(' '.join([('NEG','Z','CZ')[len(ws)],*[f'q{w}'for w in ws],f'if b{bit}']))
        if h['cube']:
            c=h['cube']['cut'];assert c in (i,j) or depth[c]==0
            actions[c].extend(cubic_frame(h['cube']['controls'],bit))
    for pos,terms in joints.items():
        for index,u in enumerate(terms):
            assert all(not multiply(joint_anf[u],joint_anf[v])for v in terms[:index])
        b=nb;nb+=1
        before[0].append(f'BIT_INVERT b{b}')
        # This conditional bit is read inside the native gate's own frame only.
        before[pos].extend(f'BIT_INVERT b{b} if b{w}'for w in terms)
        actual=ops[pos].line
        actions[pos]+=([f'PUSH_CONDITION if b{b}',actual,'POP_CONDITION'])
    out=['# '+NOTICE]
    for i,o in enumerate(ops):
        out+=before[i]+actions[i]
        if i not in joints:out.append(o.line)
        out+=after[i]
    out+=before[len(ops)]+actions[len(ops)]
    text='\n'.join(out)+'\n';a.out.mkdir(exist_ok=True,parents=True)
    (a.out/'candidate.kmx').write_text(text)
    m=kickmix.Circuit(text);assert m.num_qubits==base.num_qubits
    f=a.out/'invsqrt.kmb';m.to_file(str(f),format='kmb');print('sha256',hashlib.sha256(f.read_bytes()).hexdigest(),flush=True)


if __name__=='__main__':main()
