# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0. Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.
"""Emit a delayed multi-wire Clifford correction for a deliberately omitted native product."""
import argparse
import hashlib
import json
from pathlib import Path
import kickmix
from build_angles import NOTICE

def gates(repair):
    if not repair:
        return []
    targets=repair['target'];controls=repair['controls'];anchor=targets[0]
    assert len(targets)==len(set(targets)) and len(set(targets)&set(controls))%2==0
    frame=[f'CX q{anchor} q{q}' for q in targets[1:]]
    action=([f'X q{anchor}'] if repair['invert'] else [])+[f'CX q{w} q{anchor}' for w in controls if w!=anchor]
    return frame+action+list(reversed(frame))

def main():
    p=argparse.ArgumentParser()
    for name in ('native','spec','out'):p.add_argument(name,type=Path)
    a=p.parse_args();r=json.loads(a.spec.read_text());assert hashlib.sha256(a.native.read_bytes()).hexdigest()==r['source_text_sha256']
    ops=[line.split('#',1)[0].strip() for line in a.native.read_text().splitlines()];ops=[s for s in ops if s]
    assert ops[r['start']]==r['gate'] and r['start']<r['end']
    stock=kickmix.Circuit(a.native.read_text())
    assert stock.num_qubits==43
    replacement=gates(r['repair'])
    lines=['# '+NOTICE]+ops[:r['start']]+ops[r['start']+1:r['end']]+replacement+ops[r['end']:]
    a.out.mkdir(parents=True,exist_ok=True);raw='\n'.join(lines)+'\n';(a.out/'candidate.kmx').write_text(raw)
    c=kickmix.Circuit(raw);assert c.num_qubits==43
    c.to_file(str(a.out/'invsqrt.kmb'),format='kmb')
    print('deleted',r['start'],r['gate'],'Clifford repair at',r['end'],replacement,hashlib.sha256((a.out/'invsqrt.kmb').read_bytes()).hexdigest(),flush=True)

if __name__=='__main__':main()
