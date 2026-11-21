# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
"""Expand the live interpolation width one bit per signed coefficient row.

The first copy saves the original high bit for later phase retirement. The second
copy also replays a measured carry, including the pre-existing conditional phase.
This is a port of this project's two F16+ window passes to the 38a1 source build.
"""
import json
import re
from pathlib import Path
from types import SimpleNamespace
def parse_line(s):
    return SimpleNamespace(name=s.split()[0],qs=tuple(map(int,re.findall(r"q(\d+)",s))),bs=tuple(map(int,re.findall(r"b(\d+)",s))))
def payments():
    return json.loads(Path(__file__).with_name('coefficient_phase.json').read_text())

def locate(src,oplines,l,h):
    rows=oplines[l-1:h];starts=[i for i,o in enumerate(src)if o==rows[0] and src[i:i+len(rows)]==rows]
    if len(starts)!=1:raise AssertionError(('lost native anchor',l,h,len(starts)))
    return starts[0]
def first_window(body,oplines):
    reg=[21,34,36,0,30,32,28,35];r2=[16,17,18,0,21,29,27,9]
    first=locate(body,oplines,3175,3570);second=locate(body,oplines,24865,24884)
    old=oplines[3174:3570];rec=[];mods={3175:[f'CX q{reg[2]} q29']};removed=0
    intervals=[(3204,3218),(3264,3275),(3330,3338),(3402,3407),(3480,3482)]
    for i,(lo,hi) in enumerate(intervals):
        w=i+3;sign=10+i;v=reg[w-1];nxt=reg[w];s=29;tmp=20
        prior=parse_line(oplines[lo-1]);c=prior.qs[0];assert prior.name=='CCX' and prior.qs[1]==v
        ms=[parse_line(z)for z in oplines[lo-1:hi] if z.startswith('HMR')];assert ms[0].qs==[c]or ms[0].qs==(c,)
        prog=[f'CX q{c} q{v}',f'HMR q{c} b{ms[0].bs[0]}']+[f'BIT_STORE0 b{op.bs[0]}'for op in ms[1:]]
        mods[lo]=prog
        for j in range(lo+1,hi+1):mods[j]=[]
        fmask=[f'CX q{sign} q{s}',f'CX q{sign} q{v}',f'X q{v}']
        new=[f'CX q{nxt} q{tmp}']+fmask+[f'CCX q{s} q{v} q{nxt}']+fmask[::-1]+[f'HMR q{s} b{28000+i}',f'SWAP q{tmp} q{s}']
        assert oplines[hi+7]==f'CX q{sign} q35'
        mods[hi+8]=[oplines[hi+7]]+new
        add=sum(z.startswith('CCX')for z in oplines[lo-1:hi])-1;removed+=add
        rec.append([i,add,[x.bs[0]for x in ms[1:]]])
    replacement=[s for i in range(3175,3571)for s in mods.get(i,[oplines[i-1]])]
    body[second:second]=[f'Z q{r2[i+2]} if b{28000+i}'for i in range(5)]
    body[first:first+len(old)]=replacement
    return body

def second_window(raw,oplines):
    base=locate(raw,oplines,24865,24884);end=locate(raw,oplines,25266,25278);target=locate(raw,oplines,29585,29601)+10
    d=[16,17,18,0,21,29,27,9];new={};old=oplines
    def setblock(l,h,g):
        new[l]=g
        for j in range(l+1,h+1):new[j]=[]
    new[24865]=[old[24864],'CX q35 q9','CX q18 q9']
    # q9 holds original A2 and q35 still holds original A7. The three-bit accumulator needs only one live carry.
    aa,ci,y0,y1,y2=28,33,16,17,18
    add=[f'CX q{aa} q{y0}',f'CX q{aa} q{ci}',f'CCX q{ci} q{y0} q{aa}',f'CCX q{aa} q{y1} q{y2}',f'CX q{aa} q{y1}',f'CCX q{ci} q{y0} q{aa}',f'CX q{aa} q{ci}',f'CX q{ci} q{y0}']
    frame=[f'CX q10 q{w}'for w in [y0,y1,y2]]
    clear=[old[24888]]+old[24890:24896]
    g=frame+add+frame+clear+['BIT_STORE0 b8002']+[f'BIT_STORE0 b{j}'for j in (190,189,188,187,186,185)]
    # Capture c3 for the fourth original carry's paid historical phase.
    s=9;v=18;sign=10;nxt=0;tmp=33
    mask=[f'CX q{sign} q{s}',f'CX q{sign} q{v}',f'X q{v}']
    g+=mask+[f'CCX q{s} q{v} q{tmp}']+mask[::-1]
    g+=['BIT_STORE0 b28019','BIT_INVERT b28019 if b366','PUSH_CONDITION if b365','BIT_INVERT b28019 if b367','POP_CONDITION','CX q10 q0','PUSH_CONDITION if b28019','CCZ q15 q33 q0','POP_CONDITION','CX q10 q0']
    g+=['HMR q9 b28010','CX q0 q9','CX q33 q0','CX q9 q33','CX q0 q33']
    setblock(24875,24933,g)
    intervals=[(24977,24999,25007),(25060,25068,25076),(25137,25151,25159),(25230,25232,25265)]
    for i,(lo,hi,after)in enumerate(intervals,1):
        w=i+3;sign=10+i;v=d[w-1];nxt=d[w];c=parse_line(old[lo-1]).qs[0]
        h=[parse_line(z)for z in old[lo-1:hi]if z.startswith('HMR')];assert h[0].qs[0]==c,(i,v,c,h)
        setblock(lo,hi,[f'CX q{c} q{v}',f'HMR q{c} b{h[0].bs[0]}']+[f'BIT_STORE0 b{op.bs[0]}'for op in h[1:]])
        # Above the active window q9 temporarily stores an original A_j. Both original sign flips are omitted during that interval.
        sel=next(j for j in range(lo-70,lo)if old[j-1]==f'CX q{sign} q9')
        new[sel]=[];snap=9;tmp=33
        if i==4:
            calc=['SWAP q9 q33','CX q35 q9'];snap=33
            fmask=[f'CX q{sign} q{snap}',f'CX q{sign} q{v}',f'X q{v}']
            calc+=fmask+[f'CCX q{snap} q{v} q{nxt}']+fmask[::-1]+[f'HMR q{snap} b{28010+i}']
        else:
            fmask=[f'CX q{sign} q{snap}',f'CX q{sign} q{v}',f'X q{v}']
            calc=[f'CX q{nxt} q{tmp}']+fmask+[f'CCX q{snap} q{v} q{nxt}']+fmask[::-1]+[f'HMR q{snap} b{28010+i}',f'SWAP q{tmp} q{snap}']
        assert old[after-1]==f'CX q{sign} q9'
        new[after]=calc
    regenerated=[s for j in range(24865,25266)for s in new.get(j,[old[j-1]])]
    assert raw[base:end]==old[24864:25265]
    raw[target:target]=payments();raw[base:end]=regenerated
    return raw

def optimize(raw):
    raw=raw.splitlines()
    slots=['']*29602
    # 1-indexed stable names of the source arithmetic rows; only regenerated gates
    # from the incoming circuit supply the contents of each row.
    for a,b,start in [(3175,3570,3170),(24865,25278,24560),(29585,29601,29215)]:
        slots[a-1:b]=raw[start:start+b-a+1]
    raw=first_window(raw,slots)
    raw=second_window(raw,slots)
    return '\n'.join(raw)+'\n'
