# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro,
# Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science
# supporting the research.
"""Bounded constructive search for a late43-owner Boolean chart.

An omitted logical value is an exact ANF in physical owners. A reversible
chart change may exchange it with a variable occurring only linearly. All
emitted gates are literal X/CX/CCX/SWAP; no extra owner is granted. This
bounded beam is constructive research, never a negative family certificate.
"""
from pathlib import Path
from dataclasses import dataclass
import hashlib,json,sys,time
from map_incumbent_width import BASE,NOTICE,Program,sha
NATIVE=BASE/'agents/temporal_merges/q43_integrated_width_base_v1/candidate_text.kmx'
START,STOP=31119,31390

def px(a,b):return a^b
def pm(a,b):
    out=set()
    for x in a:
        for y in b:
            z=x|y
            if z in out:out.remove(z)
            else:out.add(z)
    return frozenset(out)
def substitute(f,t,d):
    b=1<<t;selected=frozenset(m^b for m in f if m&b)
    return f^pm(selected,d)
def bits(m):
    while m:
        b=m&-m;yield b.bit_length()-1;m^=b

def polynomial_gates(f,target):
    if any(m>>target&1 for m in f) or any(m.bit_count()>2 for m in f):return None
    linear=sum(m for m in f if m.bit_count()==1);constant=0 in f
    quad=set(m for m in f if m.bit_count()==2);products=[]
    while quad:
        edge=min(quad);i,j=list(bits(edge));a=b=0
        for m in quad:
            if m>>j&1:a^=m^(1<<j)
            if m>>i&1:b^=m^(1<<i)
        assert a>>i&1 and b>>j&1 and not(a>>j&1) and not(b>>i&1)
        product=pm(frozenset(1<<k for k in bits(a)),frozenset(1<<k for k in bits(b)))
        for m in product:
            if m.bit_count()==2:
                if m in quad:quad.remove(m)
                else:quad.add(m)
            else:linear^=m
        products.append((a,b,i,j))
    gates=[]
    if constant:gates.append(f'X q{target}')
    for k in bits(linear):gates.append(f'CX q{k} q{target}')
    for a,b,i,j in products:
        prep=[f'CX q{k} q{i}' for k in bits(a) if k!=i]+[f'CX q{k} q{j}' for k in bits(b) if k!=j]
        gates+=prep+[f'CCX q{i} q{j} q{target}']+prep[::-1]
    return gates,len(products)

@dataclass
class State:
    missing:int
    mapping:tuple
    f:frozenset
    gates:tuple=()
    cost:int=0
    actions:tuple=()

def pivot(s,t,i):
    bit=1<<t
    if bit not in s.f or any(m&bit for m in s.f if m!=bit):return None
    old=s.mapping.index(t);g=s.f^{bit};res=polynomial_gates(g,t)
    if res is None:return None
    gates,cost=res;mapping=list(s.mapping);mapping[s.missing]=t;mapping[old]=-1
    return State(old,tuple(mapping),s.f,s.gates+tuple(gates),s.cost+cost,s.actions+(dict(cut=i,kind='chart_exchange',old_omitted=s.missing,new_omitted=old,physical=t,added_ANDs=cost),))

def apply_regular(s,kind,args,i):
    if kind in ('X','CX','CCX'):
        target=args[-1];controls=args[:-1];d=frozenset([0])
        for c in controls:
            d=pm(d,s.f if c==s.missing else frozenset([1<<s.mapping[c]]))
        if target==s.missing:return State(s.missing,s.mapping,s.f^d,s.gates,s.cost,s.actions)
        t=s.mapping[target]
        if s.missing in controls:
            res=polynomial_gates(d,t)
            if res is None:return None
            gates,cost=res
        else:
            gates=[kind+' '+' '.join('q'+str(s.mapping[x]) for x in args)];cost=kind=='CCX'
        f=substitute(s.f,t,d)
        return State(s.missing,s.mapping,f,s.gates+tuple(gates),s.cost+cost,s.actions)
    raise AssertionError(kind)

def key(s):return(s.missing,s.mapping,s.f)
def prune(states,limit=400):
    found={}
    for s in states:
        if s is None or s.cost>12:continue
        k=key(s)
        if k not in found or (s.cost,len(s.gates))<(found[k].cost,len(found[k].gates)):found[k]=s
    return sorted(found.values(),key=lambda s:(s.cost,len(s.gates),len(s.f),s.missing))[:limit]

def finish(s,hmr,i):
    q=int(hmr.arguments[0][1:]);outcome=hmr.arguments[1];options=[]
    if s.missing==q:
        options.append(State(q,s.mapping,frozenset(),s.gates+(f'BIT_STORE0 {outcome}',),s.cost,s.actions+(dict(cut=i,kind='omit_virtual_HMR_branch_zero',owner=q),)))
    else:
        t=s.mapping[q]
        if not any(m>>t&1 for m in s.f):
            options.append(State(s.missing,s.mapping,s.f,s.gates+(f'HMR q{t} {outcome}',),s.cost,s.actions))
        p=pivot(s,t,i)
        if p is not None:
            options.append(State(q,p.mapping,frozenset(),p.gates+(f'BIT_STORE0 {outcome}',),p.cost,p.actions+(dict(cut=i,kind='omit_virtual_HMR_branch_zero',owner=q),)))
    result=[]
    for s in options:
        mapping=list(s.mapping);free=(set(range(44))-set(mapping))-{ -1 };assert len(free)==1
        target=next(iter(free));res=polynomial_gates(s.f,target)
        if res is None:continue
        extra,cost=res;mapping[s.missing]=target;gates=list(s.gates)+extra
        # The logical reset has provided a zero value. Restore canonical names
        # with physical SWAPs, which keep the nonzero occupancy unchanged.
        for logical in range(44):
            physical=mapping[logical]
            if physical==logical:continue
            gates.append(f'SWAP q{physical} q{logical}')
            mapping=[logical if x==physical else physical if x==logical else x for x in mapping]
        assert mapping==list(range(44))
        result.append(State(-1,tuple(mapping),frozenset(),tuple(gates),s.cost+cost,s.actions))
    return result

def main():
    began=time.monotonic();assert sha(NATIVE)=='23f2ecd3f88f4b72d7657abae0027511d64ec0201d4985e004608e15b11144c3'
    p=Program(NATIVE.read_text());assert all(o.condition is None for o in p.operations[START:STOP])
    assert p.operations[STOP-1].kind=='HMR'
    mapping=list(range(44));mapping[21]=-1;states=[State(21,tuple(mapping),frozenset())];i=START;trace=[]
    while i<STOP-1 and states:
        op=p.operations[i];kind=op.kind;args=[int(x[1:]) for x in op.arguments]
        # Recognize literal three-CX SWAPs and change logical ownership only.
        if kind=='CX' and i+2<STOP:
            b,c=p.operations[i+1:i+3]
            if b.kind==c.kind=='CX' and b.arguments==op.arguments[::-1] and c.arguments==op.arguments:
                kind='SWAP';advance=3
            else:advance=1
        else:advance=1
        if kind=='SWAP':
            a,b=args;new=[]
            for s in states:
                m=list(s.mapping);m[a],m[b]=m[b],m[a];missing=b if s.missing==a else a if s.missing==b else s.missing
                new.append(State(missing,tuple(m),s.f,s.gates,s.cost,s.actions))
            states=new
        else:
            new=[]
            for s in states:
                choices=[s]
                if s.missing in args[:-1] or kind=='CCX':
                    choices += [r for t in range(44) if t in s.mapping and (r:=pivot(s,t,i)) is not None]
                new.extend(apply_regular(r,kind,args,i) for r in choices)
            states=prune(new)
        if i%20==0 or not states:
            rec=dict(operation=i,states=len(states),minimum_paid=min((s.cost for s in states),default=None),max_degree=max((max((m.bit_count() for m in s.f),default=0) for s in states),default=0));trace.append(rec);print(json.dumps(rec),flush=True)
        i+=advance
    finals=prune([v for s in states for v in finish(s,p.operations[STOP-1],STOP-1)]) if states else []
    out=BASE/'root/q43_late_virtual_owner_v1';out.mkdir(exist_ok=True)
    report=dict(notice=NOTICE,status='CONSTRUCTIVE_FORMAL_CHART_EMITTER_FOUND_REQUIRES_NATIVE_PROOF' if finals else 'BOUNDED_CONSTRUCTIVE_CHART_SEARCH_NO_EMITTER',parent_native_sha256=sha(NATIVE),source_sha256=sha(Path(__file__)),parent_interval=[START,STOP],beam_cap=400,paid_cap=12,trace=trace,final_count=len(finals),complete_negative_scope_claimed=False,seconds=time.monotonic()-began)
    if finals:
        s=finals[0];text=NATIVE.read_text();lines=text.splitlines();operation_line=[];j=0
        for k,line in enumerate(lines):
            if line.strip() and not line.strip().startswith(('#','INFO_TAG','DEBUG_PRINT','APPEND_TO_REGISTER','REGISTER')):operation_line.append(k)
        assert len(operation_line)==len(p.operations)
        changed='\n'.join(['# '+NOTICE]+lines[:operation_line[START]]+list(s.gates)+lines[operation_line[STOP]:])+'\n'
        native=out/'candidate_text.kmx';native.write_text(changed)
        report.update(candidate_native_sha256=sha(native),new_block_operations=len(s.gates),modelled_block_ANDs=s.cost,original_block_ANDs=1,modelled_added_Toffolis=s.cost-1,actions=s.actions,candidate_interval=[START,START+len(s.gates)],gates=list(s.gates))
    (out/'REPORT.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ('trace','gates','actions')},indent=2))
if __name__=='__main__':main()
