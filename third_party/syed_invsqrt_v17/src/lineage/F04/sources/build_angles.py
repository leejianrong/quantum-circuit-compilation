# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0. Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.
"""Translate a gauge-preserving refit on our hash-bound Stack-4 physical circuit."""
import argparse
from fractions import Fraction
import hashlib
import io
import json
from pathlib import Path
import kickmix as km
NOTICE="Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0. Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research."
STACK_TEXT="33dfb8065152af4a589aa4ca96f4eb93fd269fa461d5bf159574d9c736403a7c"
STACK_BINARY="fd12a9f4c19598911bbc45201720dfa050331324600cab012a6ff5faf3e3ea14"
STACK_FIT="6bcc83e18e1f7a754e1934b109959b82fc44760a61dd2789a1f346e02a46c053"
def digest(b):return hashlib.sha256(b).hexdigest()
def decimal(h):
    h%=2;n=h.denominator.bit_length()-1;assert 1<<n==h.denominator
    if not n:return str(h.numerator)
    s=str(h.numerator*5**n).zfill(n+1);s=(s[:-n]+'.'+s[-n:]).rstrip('0').rstrip('.')
    assert Fraction(s)==h;return s
def main():
    ap=argparse.ArgumentParser()
    for k in ["parent","parent_fit","fit","out"]:ap.add_argument(k,type=Path)
    a=ap.parse_args(); native=a.parent.read_bytes(); assert digest(native)==STACK_TEXT
    assert digest(a.parent_fit.read_bytes())==STACK_FIT
    old=json.loads(a.parent_fit.read_text()); new=json.loads(a.fit.read_text()); flip=old["gauge"]["flipped_rotation_sites"]
    assert flip==new["gauge"]["flipped_rotation_sites"] and new["gauge"]["T_site_flipped"]
    assert new["new_angles_units50"][-1]==((1<<47)-sum(new["new_angles_units50"][j] for j in flip))% (1<<50)
    def half(ang,j):return Fraction((-1 if j in flip else 1)*ang[j],1<<49)%2
    match={half(old["new_angles_units50"],j):j for j in range(34)}
    assert len(match)==34
    buf=io.BytesIO();km.Circuit(native.decode()).to_file(buf,format="kmb")
    assert digest(buf.getvalue())==STACK_BINARY
    out=["# "+NOTICE]; seen=set();depth=0
    for line in native.decode().splitlines():
        t=line.split()
        if t and t[0]=="PUSH_CONDITION": depth+=1
        if t and t[0]=="POP_CONDITION": depth-=1
        if t and t[0]=="Z_POW" and (h:=Fraction(t[2])) in match:
            j=match[h];assert j not in seen and depth==0 and len(t)==3
            seen.add(j); line=f"Z_POW {t[1]} {decimal(half(new['new_angles_units50'],j))}"
        out.append(line)
    assert len(seen)==34 and depth==0
    txt="\n".join(out)+"\n";a.out.mkdir(parents=True,exist_ok=True)
    (a.out/"candidate.kmx").write_text(txt)
    km.Circuit(txt).to_file(str(a.out/"invsqrt.kmb"),format="kmb")
    print(digest((a.out/"invsqrt.kmb").read_bytes()))
if __name__=="__main__":main()
