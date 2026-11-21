# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0. Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2 and Opus 5.5), with Claude Science supporting the research.
"""Replace the physical rotation angles on the authenticated F03 binary without changing any other instruction."""
import argparse,hashlib,io,json
from fractions import Fraction
from pathlib import Path
import kickmix as km
from build_angles import decimal,NOTICE
def main():
    ap=argparse.ArgumentParser()
    for k in ('parent','parent_fit','fit','out'):ap.add_argument(k,type=Path)
    a=ap.parse_args();native=a.parent.read_text();old=json.loads(a.parent_fit.read_text());f=json.loads(a.fit.read_text())
    c=km.Circuit(native);bb=io.BytesIO();c.to_file(bb,format='kmb');assert hashlib.sha256(bb.getvalue()).hexdigest()=='3f95a2aa8c3e11cf5edc4750dc154be3bc427ac01f61feb0f82fdcb10e3066e6'
    assert hashlib.sha256(a.parent_fit.read_bytes()).hexdigest()==f['parent_fit_sha256']
    flip=set(old['gauge']['flipped_rotation_sites']);p=f['phase_precision'];assert f['gauge']['constant_units']==((1<<(p-3))-sum(f['angles_units'][j]for j in flip))%(1<<p)
    oldset={Fraction((-1 if j in flip else 1)*ang,1<<49)%2:j for j,ang in enumerate(old['new_angles_units50'][:-1])};newset={};seen=set()
    lines=['# '+NOTICE]
    for line in native.splitlines():
        words=line.split()
        if len(words)==3 and words[0]=='Z_POW' and Fraction(words[2])%2 in oldset:
            j=oldset[Fraction(words[2])%2];assert j not in seen;seen.add(j)
            val=Fraction((-1 if j in flip else 1)*f['angles_units'][j],1<<(p-1))%2
            line=f'Z_POW {words[1]} {decimal(val)}';newset[val]=j
        lines.append(line)
    assert len(seen)==len(newset)==34
    output='\n'.join(lines)+'\n';a.out.mkdir(parents=True,exist_ok=True);(a.out/'candidate.kmx').write_text(output);file=a.out/'invsqrt.kmb';km.Circuit(output).to_file(str(file),format='kmb')
    text=io.StringIO();km.Circuit.from_file(str(file)).to_file(text,format='kmx');parsed={Fraction(v.split()[2])%2 for v in text.getvalue().splitlines()if v.startswith('Z_POW ')}
    assert newset.keys()<=parsed
    print('binary',hashlib.sha256(file.read_bytes()).hexdigest(),'physical generic sites',len(newset),flush=True)
if __name__=='__main__':main()
