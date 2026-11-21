# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0. Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.
"""Emit the priced schedule with movable exponent-product lifetimes and reversible in-place angular features."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import kickmix as km
from build_walk import Walk,START,END,FLAGS,N,xor_sequence,product_gates,NOTICE

class JointWalk(Walk):
    def edge(self,i,opening):
        s,l,r=self.edges[i]
        if [s,l,r] in self.plan.get('remove',[]):
            if self.plan['common_swap']:self.emit(f'SWAP q{self.word[l]} q{self.word[r]}')
            return
        super().edge(i,opening)
    def in_place(self,row,w):
        tr=xor_sequence(w,row['chart']);f=row['form'];t=w[-1];seq=[]
        if f['linear']&1:seq.append(f'X q{t}')
        seq.extend(f'CX q{x} q{t}'for i,x in enumerate(w[:-1],1)if f['linear']>>i&1)
        for l,r in f['products']:seq.extend(product_gates(w[:-1],l,r,t))
        return tr+seq,t
    def feature(self,j,t):
        row=self.plan['feature_options'][j];form=row['form']
        w=FLAGS+[self.p]if row['with_product']else FLAGS.copy()
        assert None not in w
        args=w+[t]
        if row.get('with_sibling'):
            v=(j-self.plan['offset'])%N;nb=(self.plan['axes'][-1]-v)%N
            assert row['neighbor']==(nb+self.plan['offset'])%N
            args.append(self.word[nb])
            if row.get('needs_hold'):
                e=self.edges.index((4,min(v,nb),max(v,nb)));args.append(self.held[e])
        self.shear(row['extra'])
        if row['kind']=='direct':
            z=self.value(form,args);self.rotate(z,27+j);self.erase(z,form,args)
        elif row['kind']=='threshold':
            z=self.value(form,w);ft={'linear':0,'products':[[1,2]]}
            a=self.value(ft,[t,z]);self.rotate(a,27+j);self.erase(a,ft,[t,z]);self.erase(z,form,w)
        elif row['kind']=='reversible':
            gates,z=self.in_place(row,args);self.emit(*gates);self.rotate(z,27+j);self.emit(*gates[::-1])
        elif row['kind']=='reversible_threshold':
            gates,z=self.in_place(row,w);self.emit(*gates);ft={'linear':0,'products':[[1,2]]}
            a=self.value(ft,[z,t]);self.rotate(a,27+j);self.erase(a,ft,[z,t]);self.emit(*gates[::-1])
        else:raise ValueError(row['kind'])
        self.shear(row['extra'])
    def make(self):
        if 'helper_intervals' in self.plan:
            return self.make_helpers()
        ss,ee=self.plan['intervals'][self.plan['special']]
        if ss:self.borrow()
        ps=self.plan['product_steps'];pf={'linear':0,'products':[[2,12]]}
        for n,v in enumerate(self.plan['order']):
            if n==ss and ss:self.repay()
            for i,(s,_)in enumerate(self.plan['intervals']):
                if s==n:self.edge(i,True)
            if ps[n] and (not n or not ps[n-1]):self.p=self.value(pf,FLAGS)
            j=(v+self.plan['offset'])%N;t=self.word[v]
            self.rotate(t,j)
            if j<8:self.feature(j,t)
            if ps[n]and(n==N-1 or not ps[n+1]):self.erase(self.p,pf,FLAGS);self.p=None
            for i in reversed(range(len(self.edges))):
                if self.plan['intervals'][i][1]==n:self.edge(i,False)
            if n==ee and ee<N-1:self.borrow()
        if ee<N-1:self.repay()
        assert self.free=={9,21,29} and not self.held and self.p is None
        self.emit('CZ q23 q25')
        count=sum(v.split()[0]in('CCX','CSWAP','CCZ')for v in self.lines)
        assert count==self.plan['price'],(count,self.plan['price'])
        return self.lines


    def make_helpers(self):
        p=self.plan;ss,ee=p['intervals'][p['special']]
        if ss:self.borrow()
        arrivals={start:(int(h),end)for h,start,end in p['helper_intervals']}
        active=None;end=-1;formula=None
        for i,v in enumerate(p['order']):
            if i==ss and ss:self.repay()
            for g,(first,_)in enumerate(p['intervals']):
                if first==i:self.edge(g,True)
            if i in arrivals:
                assert self.p is None
                active,end=arrivals[i]
                formula=p.get('helper_forms',{}).get(str(active),{'linear':0,'products':[p['helper_factors'][str(active)]]})
                self.p=self.value(formula,FLAGS)
            j=(v+p['offset'])%N;t=self.word[v];self.rotate(t,j)
            if j<8:
                want=p['feature_options'][j]['helper_id']
                assert not want or want==active
                self.feature(j,t)
            if i==end:
                self.erase(self.p,formula,FLAGS);self.p=None;active=None
            for g in reversed(range(len(self.edges))):
                if p['intervals'][g][1]==i:self.edge(g,False)
            if i==ee and ee<N-1:self.borrow()
        if ee<N-1:self.repay()
        assert self.free=={9,21,29} and not self.held and self.p is None
        self.emit('CZ q23 q25')
        paid=sum(z.split()[0]in('CCX','CSWAP','CCZ')for z in self.lines)
        assert paid==p['price'],(paid,p['price'])
        return self.lines

def main(walk_type=JointWalk):
    a=argparse.ArgumentParser()
    for k in ('parent','fit','plan','word','out'):a.add_argument(k,type=Path)
    a=a.parse_args();native=a.parent.read_text();b=io.BytesIO();km.Circuit(native).to_file(b,format='kmb')
    assert hashlib.sha256(b.getvalue()).hexdigest()=='225883e65dee8f6d9006a3a6ce9b21d835e5cbbfe0c55473214df2df50873b70'
    ops=[v.split('#',1)[0].strip()for v in native.splitlines()];ops=[v for v in ops if v]
    assert ops[END]=='X q0' and sum(v.split()[0]in('CCX','CSWAP','CCZ')for v in ops[START:END])==122
    plan=json.loads(a.plan.read_text());w=walk_type(plan,json.loads(a.word.read_text())['word'],json.loads(a.fit.read_text()))
    walk=w.make();text='\n'.join(['# '+NOTICE,*ops[:START],*walk,*ops[END:]])+'\n'
    a.out.mkdir(parents=True,exist_ok=True);(a.out/'candidate.kmx').write_text(text);fp=a.out/'invsqrt.kmb';km.Circuit(text).to_file(str(fp),format='kmb')
    print('new shifter',plan['price'],'Toffolis, SHA-256',hashlib.sha256(fp.read_bytes()).hexdigest())
if __name__=='__main__':main()
