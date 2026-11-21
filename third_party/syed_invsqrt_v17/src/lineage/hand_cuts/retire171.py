"""Refactor b367's AND into the product at the later native divider gate."""
from retire170 import argparse, Path, hashlib, json, sample, km


def cut_shared_171(s):
    mark='CX q29 q16\nCX q21 q16\nCCX q30 q17 q16\nBIT_INVERT b13043 if b13040\n'
    assert s.count(mark)==1 and 'b15023' not in s and 'b15024' not in s
    a=s.index(mark)
    zz='CX q21 q16\nCX q29 q16\nCX q21 q8\n'
    z=s.index(zz,a)
    b=s[a:z]
    assert b.count('CCX q30 q17 q16\n')==2
    b=b.replace('CCX q30 q17 q16\n','',1)
    for k in ['CCZ q7 q8 q16 if b13040\n','CCZ q16 q7 q8\n']:
        assert b.count(k)==1;b=b.replace(k,'')
    phase=['Z q16','CZ q16 q8','CZ q16 q7 if b13043']
    k=['CX q7 q17','CX q8 q17','CCX q30 q17 q16','CX q8 q17','CX q7 q17']
    repl=['BIT_STORE1 b15023 if b13043','BIT_STORE1 b15024 if b13040','CZ q30 q7 if b13040',*phase,*k,'CCZ q16 q7 q8',*phase]
    b=b.replace('CCX q30 q17 q16\n','\n'.join(repl)+'\n')
    s=s[:a]+b+s[z:]
    tail='CX q34 q7\nCX q34 q21\nCX q21 q30\nCX q36 q30\nCX q36 q7\nCX q7 q21\nCX q7 q21\nPOP_CONDITION\nCZ q0 q7 if b9108\n'
    assert s.count(tail)==1
    z=s.index(tail);i=s.rindex('CCX q21 q30 q7\n',z-1800,z)
    p=[];post=[]
    for flag,hs in [(15023,[15,17,18,36]),(15024,[34,36])]:
        side=['CX q7 q16',*[f'CZ q7 q{j}' for j in hs]]
        once=['CX q21 q16',*[f'CZ q21 q{j}' for j in hs]]
        if flag==15024:
            once+=['Z q21','CZ q21 q30','CZ q21 q7']
            once+=['Z_POW q21 1.75','Z_POW q30 1.75','CX q21 q30','Z_POW q30 0.25','CX q21 q30','Z_POW q7 1.5']
            post+=['Z_POW q7 0.5 if b15024']
        p += [f'PUSH_CONDITION if b{flag}',*once,*side,'POP_CONDITION']
        post += [f'PUSH_CONDITION if b{flag}',*side,'POP_CONDITION']
    return s[:i]+'\n'.join([*p,'CCX q21 q30 q7',*post])+'\n'+s[i+len('CCX q21 q30 q7\n'):]


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    src=a.input.read_text();dst=cut_shared_171(src);a.output.mkdir(parents=True,exist_ok=True)
    (a.output/'invsqrt.kmx').write_text(dst);km.Circuit(dst).to_file(str(a.output/'invsqrt.kmb'),format='kmb')
    dg=lambda f:hashlib.sha256(f.read_bytes()).hexdigest();child=dg(a.output/'invsqrt.kmb');print('built',child,flush=True)
    n=sample(src,dst);print('sample',n,flush=True);(a.output/'certificate.json').write_text(json.dumps(dict(parent=dg(a.input.with_suffix('.kmb')),child=child,shots=n),indent=2)+'\n')
