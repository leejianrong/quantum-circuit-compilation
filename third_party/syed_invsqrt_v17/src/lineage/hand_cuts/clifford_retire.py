"""Replace both guarded three-T target payments using affine equations between the two AND sites."""
from retire170 import argparse, Path, hashlib, json, sample, km


def cut_clifford(s):
    assert 'b15025' not in s
    old='CX q15 q0\nCX q8 q0\nCCX q30 q8 q16\nCX q8 q0\nCX q15 q0\n'
    a='BIT_STORE1 b15025\nBIT_STORE0 b15025 if b13035\nCZ q16 q7 if b15025\nCCX q30 q8 q16\nCZ q16 q7 if b15025\n'
    assert s.count(old)==1
    s=s.replace(old,old.replace('CCX q30 q8 q16\n',a))
    old='CX q7 q17\nCX q8 q17\nCCX q30 q17 q16\nCX q8 q17\nCX q7 q17\nCCZ q16 q7 q8'
    a='CZ q16 q7 if b13040\nCCX q30 q17 q16\nCZ q16 q7 if b13040\n'
    assert s.count(old)==1
    s=s.replace(old,old.replace('CCX q30 q17 q16\n',a))
    t1='CZ q21 q7\nZ_POW q21 1.75\nZ_POW q30 1.75\nCX q21 q30\nZ_POW q30 0.25\nCX q21 q30\nZ_POW q7 1.5\n'
    assert s.count(t1)==2;s=s.replace(t1,'')
    before=[];after=[]
    for f,js in [(15022,[15,34,36]),(15024,[15,17,18,34])]:
        line=f'Z_POW q7 0.5 if b{f}\n'
        assert s.count(line)==1;s=s.replace(line,'')
        lead=[f'PUSH_CONDITION if b{f}'];side=[f'CZ q7 q{j}' for j in js]
        low=['Z q21','CZ q21 q30',*[f'CZ q21 q{j}' for j in js]]
        before += [*lead,*low,*side,'POP_CONDITION']
        after += [*lead,*side,'POP_CONDITION']
    tail='CX q34 q7\nCX q34 q21\nCX q21 q30\nCX q36 q30\nCX q36 q7\nCX q7 q21\nCX q7 q21\nPOP_CONDITION\nCZ q0 q7 if b9108\n'
    assert s.count(tail)==1
    z=s.index(tail);i=s.rindex('CCX q21 q30 q7\n',z-1800,z)
    return s[:i]+'\n'.join(before+['CCX q21 q30 q7']+after)+'\n'+s[i+len('CCX q21 q30 q7\n'):]

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    src=a.input.read_text();dst=cut_clifford(src);a.output.mkdir(parents=True,exist_ok=True)
    (a.output/'invsqrt.kmx').write_text(dst);km.Circuit(dst).to_file(str(a.output/'invsqrt.kmb'),format='kmb')
    dg=lambda f:hashlib.sha256(f.read_bytes()).hexdigest();child=dg(a.output/'invsqrt.kmb');print('built',child,flush=True)
    n=sample(src,dst);print('sample',n,flush=True);(a.output/'certificate.json').write_text(json.dumps(dict(parent=dg(a.input.with_suffix('.kmb')),child=child,shots=n),indent=2)+'\n')
