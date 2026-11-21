# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0. Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.
"""Build a reversible ring walk with a temporarily borrowed constant wire and measured AND erasures."""
import argparse
import hashlib
import io
import json
from fractions import Fraction
from pathlib import Path
import kickmix as km
from build_angles import NOTICE,decimal

START,END=8539,9394
FLAGS=list(range(22,26))
N=27

def xor_sequence(wires,rows):
    """Row-reduce a requested reversible linear map; return its circuit from identity."""
    n=len(rows);v=rows.copy();reduction=[]
    for i in range(n):
        p=next(j for j in range(i,n) if v[j]>>i&1)
        if p!=i:
            v[i],v[p]=v[p],v[i]
            reduction.append(f'SWAP q{wires[i]} q{wires[p]}')
        for j in range(n):
            if i!=j and v[j]>>i&1:
                v[j]^=v[i];reduction.append(f'CX q{wires[i]} q{wires[j]}')
    assert v==[1<<i for i in range(n)]
    return reduction[::-1]

def complete(forms,n,allowed=None):
    rows=[];span={0}
    for v in [*forms,*(allowed if allowed is not None else (1<<i for i in range(n)))]:
        if v in span:continue
        rows.append(v);span|={u^v for u in span}
        if len(rows)==n:break
    assert rows[:len(forms)]==forms and len(rows)==n,(forms,rows)
    return rows

def product_gates(w,l,r,target):
    tr=xor_sequence(w,complete([l,r],len(w)))
    return tr+[f'CCX q{w[0]} q{w[1]} q{target}']+tr[::-1]

def monomials(form,wires):
    terms=set()
    def flip(x):terms.symmetric_difference_update([tuple(sorted(set(x)))])
    for i in range(len(wires)+1):
        if form['linear']>>i&1:flip([]if not i else [wires[i-1]])
    for l,r in form['products']:
        for i,x in enumerate(wires):
            if l>>i&1:
                for j,y in enumerate(wires):
                    if r>>j&1:flip([x,y])
    return sorted(terms)

class Walk:
    def __init__(self,plan,word,f):
        self.plan=plan;self.word=word;self.fit=f;self.lines=[]
        self.free={9,21,29};self.held={};self.p=None;self.b=13000
        self.edges=[(s,l,(c-l)%N) for s,c in enumerate(plan['axes']) for l in range(N) if l<(c-l)%N]
        self.selected=set(plan['held'])
    def emit(self,*ops):self.lines.extend(ops)
    def take(self):
        assert self.free,(len(self.lines),self.held,self.p)
        t=min(self.free);self.free.remove(t);return t
    def measure(self,w):
        m=self.b;self.b+=1;self.emit(f'HMR q{w} b{m}');return m
    def erase(self,t,form,w):
        m=self.measure(t)
        for term in monomials(form,w):
            op=('NEG','Z','CZ')[len(term)]
            self.emit(' '.join([op,*[f'q{x}'for x in term],f'if b{m}']))
        self.free.add(t)
    def value(self,form,w):
        t=self.take();a=form['linear']
        if a&1:self.emit(f'X q{t}')
        for i,x in enumerate(w):
            if a>>(i+1)&1:self.emit(f'CX q{x} q{t}')
        for l,r in form['products']:self.emit(*product_gates(w,l,r,t))
        return t
    def ctrl(self,s):
        mask=self.plan['controls'][s]
        picked=[x for i,x in enumerate(FLAGS,1)if mask>>i&1]
        a=picked[0];tr=[f'CX q{x} q{a}'for x in picked[1:]]
        if mask&1:tr.append(f'X q{a}')
        return a,tr
    def edge(self,i,opening):
        s,u,v=self.edges[i];a,b=self.word[u],self.word[v];c,tr=self.ctrl(s)
        self.emit(*tr)
        if i in self.selected:
            if opening:
                t=self.take();self.held[i]=t
                self.emit(f'CX q{a} q{b}',f'CCX q{c} q{b} q{t}',f'CX q{a} q{b}',f'CX q{t} q{a}',f'CX q{t} q{b}')
            else:
                t=self.held.pop(i);self.emit(f'CX q{t} q{a}',f'CX q{t} q{b}')
                m=self.measure(t);self.emit(f'CZ q{c} q{a} if b{m}',f'CZ q{c} q{b} if b{m}')
                self.free.add(t)
        elif i==self.plan['special'] and not opening:
            keeper=self.word[26];other=a if b==keeper else b;assert keeper in (a,b)
            self.emit(f'CX q{keeper} q{other}');m=self.measure(keeper)
            self.emit(f'NEG if b{m}',f'CZ q{c} q{other} if b{m}',f'X q{keeper}',f'CX q{keeper} q{other}')
        else:self.emit(f'CSWAP q{c} q{a} q{b}')
        self.emit(*tr[::-1])
    def borrow(self):
        c=self.word[26];assert c not in self.free;self.emit(f'X q{c}');self.free.add(c)
    def repay(self):
        c=self.word[26]
        if c not in self.free:
            pos=self.take();self.emit(f'SWAP q{c} q{pos}')
            if self.p==c:self.p=pos
            else:
                key=next(k for k,t in self.held.items()if t==c);self.held[key]=pos
        else:self.free.remove(c)
        self.emit(f'X q{c}')
    def rotate(self,t,j):
        if j==34:
            self.emit(f'X q{t}',f'Z_POW q{t} 0.25',f'X q{t}',f'Z_POW q{t} 0.5');return
        flip=j in self.fit['gauge']['flipped_rotation_sites'];val=self.fit['angles_units'][j]
        if flip:self.emit(f'X q{t}')
        self.emit(f'Z_POW q{t} {decimal(Fraction(-val if flip else val,1<<(self.fit["phase_precision"]-1)))}')
        if flip:self.emit(f'X q{t}')
    def shear(self,extra):
        if not extra:return
        d,l,r=extra
        rows=complete([l,r],4,[u for u in range(1,16)if (d&u).bit_count()%2==0]+[u for u in range(1,16)if (d&u).bit_count()%2])
        assert all((u&d).bit_count()%2==int(i==3)for i,u in enumerate(rows))
        tr=xor_sequence(FLAGS,rows);self.emit(*tr,f'CCX q{FLAGS[0]} q{FLAGS[1]} q{FLAGS[3]}',*tr[::-1])
    def feature(self,j,t):
        opt=self.plan['feature_options'][j];form=opt['form'];w=FLAGS+([]if self.p is None else[self.p]);self.shear(opt['extra'])
        if opt['kind']=='direct':
            args=w+[t];z=self.value(form,args);self.rotate(z,27+j);self.erase(z,form,args)
        elif opt['kind']=='threshold':
            z=self.value(form,w);ft={'linear':0,'products':[[1,2]]}
            a=self.value(ft,[t,z]);self.rotate(a,27+j);self.erase(a,ft,[t,z]);self.erase(z,form,w)
        self.shear(opt['extra'])
    def make(self):
        ss,ee=self.plan['intervals'][self.plan['special']]
        if ss:self.borrow()
        ps,pe=self.plan['product_span'];pform={'linear':0,'products':[[2,12]]}
        for n,v in enumerate(self.plan['order']):
            if n==ss and ss:self.repay()
            for i,(s,_)in enumerate(self.plan['intervals']):
                if s==n:self.edge(i,True)
            if n==ps:self.p=self.value(pform,FLAGS)
            j=(v+self.plan['offset'])%N;t=self.word[v]
            self.rotate(t,j)
            if j<8:self.feature(j,t)
            if n==pe:self.erase(self.p,pform,FLAGS);self.p=None
            for i in reversed(range(len(self.edges))):
                if self.plan['intervals'][i][1]==n:self.edge(i,False)
            if n==ee and ee<N-1:self.borrow()
        if ee<N-1:self.repay()
        assert self.free=={9,21,29} and not self.held and self.p is None
        self.emit('CZ q23 q25')
        cost=sum(v.split()[0]in('CCX','CSWAP','CCZ')for v in self.lines)
        assert cost==self.plan['price'],(cost,self.plan['price'])
        return self.lines

def main():
    p=argparse.ArgumentParser()
    for n in ('parent','fit','plan','word','out'):p.add_argument(n,type=Path)
    a=p.parse_args();native=a.parent.read_text();b=io.BytesIO();km.Circuit(native).to_file(b,format='kmb')
    assert hashlib.sha256(b.getvalue()).hexdigest()=='225883e65dee8f6d9006a3a6ce9b21d835e5cbbfe0c55473214df2df50873b70'
    ops=[v.split('#',1)[0].strip()for v in native.splitlines()];ops=[v for v in ops if v]
    assert ops[END]=='X q0' and sum(v.split()[0]in('CCX','CSWAP','CCZ')for v in ops[START:END])==122
    plan=json.loads(a.plan.read_text());word=json.loads(a.word.read_text())['word'];fit=json.loads(a.fit.read_text())
    walk=Walk(plan,word,fit).make();text='\n'.join(['# '+NOTICE,*ops[:START],*walk,*ops[END:]])+'\n'
    a.out.mkdir(parents=True,exist_ok=True);(a.out/'candidate.kmx').write_text(text);file=a.out/'invsqrt.kmb';km.Circuit(text).to_file(str(file),format='kmb')
    print('new walk',len(walk),'operations,',plan['price'],'Toffolis. SHA-256',hashlib.sha256(file.read_bytes()).hexdigest(),flush=True)
if __name__=='__main__':main()
