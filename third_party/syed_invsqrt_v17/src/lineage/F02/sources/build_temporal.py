# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0. Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.
"""Rebuild verified temporal Clifford replacements from a hash-bound parent."""
import argparse,hashlib,json,sys
from collections import defaultdict
from pathlib import Path
import kickmix as km
sys.path.insert(0,str(Path(__file__).resolve().parent/"own"))
from kmscan import parse_kmx
NOTICE="Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0. Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research."
def main():
    ap=argparse.ArgumentParser();ap.add_argument("parent",type=Path);ap.add_argument("spec",type=Path);ap.add_argument("out",type=Path);a=ap.parse_args()
    report=json.loads(a.spec.read_text());assert hashlib.sha256(a.parent.read_bytes()).hexdigest()==report["source_sha256"]
    ops=parse_kmx(a.parent);stock=km.Circuit(a.parent.read_text());nb=stock.num_bits
    before=defaultdict(list);after=defaultdict(list);terms=defaultdict(list);deleted=set();captured={}
    for h in report["full_domain_one_transcript_pass"]:
        k=h["op"];o=ops[k];assert o.line==h["original"] and o.name=="CCZ" and k not in deleted
        deleted.add(k);g=nb;nb+=1
        if min(pos for pos,m in h["terms"])>=k:
            before[k].append(f"BIT_INVERT b{g}"+(f" if b{o.cond}" if o.cond is not None else ""))
        else:
            fill=[]
            for mono in h["guard_ANF"]:
                ctr=[]
                for m in mono:
                    if m not in captured:
                        old=ops[m];assert old.name=="HMR"
                        b=nb;nb+=1;captured[m]=b
                        if old.cond is not None:before[m].append(f"PUSH_CONDITION if b{old.cond}")
                        after[m].append(f"BIT_INVERT b{b} if b{old.bs[0]}")
                        if old.cond is not None:after[m].append("POP_CONDITION")
                    ctr.append(captured[m])
                fill += [f"PUSH_CONDITION if b{b}" for b in ctr]+[f"BIT_INVERT b{g}"]+["POP_CONDITION"]*len(ctr)
            before[h["guard_available"]].extend(fill)
        for pos,ws in h["terms"]:
            assert pos==k or pos>=h["guard_available"]
            seq={0:"NEG",1:"Z",2:"CZ"}[len(ws)]+"".join(f" q{w}" for w in ws)
            terms[pos].append(seq+f" if b{g}")
    stream=["# "+NOTICE]
    for i,o in enumerate(ops):
        stream.extend(before[i]);stream.extend(terms[i])
        if i not in deleted:stream.append(o.line)
        stream.extend(after[i])
    stream.extend(before[len(ops)]);stream.extend(terms[len(ops)])
    out="\n".join(stream)+"\n";a.out.mkdir(parents=True,exist_ok=True);(a.out/"candidate.kmx").write_text(out)
    km.Circuit(out).to_file(str(a.out/"invsqrt.kmb"),format="kmb")
    print(hashlib.sha256((a.out/"invsqrt.kmb").read_bytes()).hexdigest(),len(deleted),flush=True)
if __name__=="__main__":main()
