# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0. Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.
"""Bring certified second-table products forward and directly settle the terminal carry phase."""
import argparse,hashlib,itertools,json,sys
from pathlib import Path
import kickmix as km
sys.path.insert(0,str(Path(__file__).resolve().parent/"own"))
from kmscan import parse_kmx
NOTICE="Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0. Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research."

def parity_gate(op,controls,target=()):
    # Choose pivots private to each parity so all controls coexist in the same Clifford frame.
    pivots=[]
    for i,mask in enumerate(controls):
        excluded=set(target).union(*(q for j,q in enumerate(controls)if j!=i))
        pivots.append(next(w for w in mask if w not in excluded))
    toggles=[f"CX q{w} q{p}" for mask,p in zip(controls,pivots)for w in mask if w!=p]
    return toggles+[op+" "+" ".join(f"q{w}" for w in [*pivots,*target])]+list(reversed(toggles))

def sign(ws):
    return ("NEG","Z","CZ")[len(ws)]+''.join(f" q{w}"for w in ws)
def main():
    ap=argparse.ArgumentParser()
    for k in ("parent","spec","out"):ap.add_argument(k,type=Path)
    a=ap.parse_args();h=json.loads(a.spec.read_text())
    assert hashlib.sha256(a.parent.read_bytes()).hexdigest()==h["source_sha256"]
    ops=parse_kmx(a.parent);s,e,late=h["early"],h["end"],h["late"];g=h["guard"]
    frame=ops[s:e];assert frame[0].line==h["old_start"] and frame[-1].line==h["old_end"]
    assert sum(o.name=="CCX" for o in frame)==2
    assert ops[s-2].line==f"BIT_STORE0 b{h['old_guard']}" and ops[s-1].line==f"BIT_INVERT b{h['old_guard']} if b{g}"
    assert all(g not in o.bs for o in ops[s:])
    streams={};start=[]
    for b in h['banks']:
        k=b['op'];old=ops[k];w=b['holder']
        assert old.line==b['expected'] and old.name=="CCX" and old.cond is None
        assert all(w not in o.qs for o in ops[e:k])
        start+=parity_gate("CCX",b['controls'],[w])
        t=old.qs[-1]
        streams[k]=[] if w==t else [f"SWAP q{w} q{t}"]
    start += [f"PUSH_CONDITION if b{g}"]+[sign(x)for x in h["early_free"]]+parity_gate("CCZ",h["cubic"])+["POP_CONDITION"]
    streams[s]=start;streams[late]=[f"PUSH_CONDITION if b{g}"]+[sign(x) for x in h["late_free"]]+["POP_CONDITION",ops[late].line]
    out=["# "+NOTICE]
    for i,o in enumerate(ops):
        if i in streams:out.extend(streams[i])
        elif not s<=i<e:out.append(o.line)
    text="\n".join(out)+"\n";a.out.mkdir(parents=True,exist_ok=True);(a.out/"candidate.kmx").write_text(text)
    km.Circuit(text).to_file(str(a.out/"invsqrt.kmb"),format="kmb")
    print(hashlib.sha256((a.out/"invsqrt.kmb").read_bytes()).hexdigest(),flush=True)
if __name__=="__main__":main()
