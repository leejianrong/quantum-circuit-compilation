# Copyright 2026 Syed Asad Ali
# SPDX-License-Identifier: Apache-2.0
"""New classical confluent key transform, including interpolation-node errors.

A mathematical witness only. The block list and chart flags are explicit
reference state, not free quantum metadata or an admitted generator layout.
"""
from __future__ import annotations
import itertools
import json
from pathlib import Path
import random
import sys
import time
import kickmix as km


class Algebra:
    def __init__(self,bits):
        self.field=km.GF2Field(bits);self.q=1<<bits
    def mul(self,a,b):return self.field.mul(a,b)
    def inv(self,a):
        assert a
        return self.field.invert(a)
    def trim(self,a):
        while len(a)>1 and a[-1]==0:a.pop()
        return a
    def add(self,a,b):
        out=a[:]+[0]*max(0,len(b)-len(a))
        for i,x in enumerate(b):out[i]^=x
        return self.trim(out)
    def product(self,a,b):
        out=[0]*(len(a)+len(b)-1)
        for i,x in enumerate(a):
            for j,y in enumerate(b):out[i+j]^=self.mul(x,y)
        return self.trim(out)
    def evaluate_polynomial(self,a,x):
        value=0
        for coefficient in reversed(a):value=self.mul(value,x)^coefficient
        return value
    def jet(self,a,x):return self.evaluate_polynomial(a,x),self.evaluate_polynomial([a[i+1] if i%2==0 else 0 for i in range(len(a)-1)] or [0],x)
    def quotient(self,a,b):
        r=a[:];q=[0]*max(1,len(a)-len(b)+1)
        while len(r)>=len(b) and r!=[0]:
            shift=len(r)-len(b);scale=self.mul(r[-1],self.inv(b[-1]));q[shift]=scale
            for i,v in enumerate(b):r[i+shift]^=self.mul(scale,v)
            self.trim(r)
        assert r==[0],(a,b,r)
        return self.trim(q)
    def interpolate(self,constraints):
        n=len(constraints);matrix=[]
        for node,derivative,value in constraints:
            row=[]
            for degree in range(n):
                row.append(self.field.pow(node,degree) if derivative==0 else
                           (self.field.pow(node,degree-1) if degree%2 else 0))
            matrix.append(row+[value])
        for col in range(n):
            pivot=next(i for i in range(col,n) if matrix[i][col])
            matrix[col],matrix[pivot]=matrix[pivot],matrix[col]
            inverse=self.inv(matrix[col][col])
            matrix[col]=[self.mul(x,inverse) for x in matrix[col]]
            for i in range(n):
                if i==col:continue
                factor=matrix[i][col]
                matrix[i]=[x^self.mul(factor,y) for x,y in zip(matrix[i],matrix[col])]
        return [row[-1] for row in matrix]
    def inverse_jet(self,jet):
        u,v,pole=jet
        if u==0:return 0,v,pole^1
        assert not pole
        inverse=self.inv(u)
        return inverse,self.mul(v,self.mul(inverse,inverse)),0
    def scale_jet(self,jet,polynomial,node):
        u,v,pole=jet;a,b=self.jet(polynomial,node)
        assert a
        if pole:return 0,self.mul(v,self.inv(a)),1
        return self.mul(a,u),self.mul(a,v)^self.mul(b,u),0
    def divide_jet(self,jet,polynomial,node):
        u,v,pole=jet;a,b=self.jet(polynomial,node)
        assert a
        if pole:return 0,self.mul(v,a),1
        inverse=self.inv(a);value=self.mul(u,inverse)
        return value,self.mul(v^self.mul(b,value),inverse),0
    def translate(self,jet,polynomial,node):
        u,v,pole=jet
        if pole:return jet
        a,b=self.jet(polynomial,node)
        return u^a,v^b,0


def modulus(algebra,nodes):
    result=[1]
    for x in nodes:result=algebra.product(result,[algebra.mul(x,x),0,1])
    return result


def from_errors(algebra,errors,nodes,M):
    # H(z)=sum e*x*(M(x)+M(z))/(x+z). This polynomial formula also
    # retains derivative information when an error is at an interpolation node.
    syndrome=[]
    for k in range(1,len(M)):
        value=0
        for x,e in errors:value^=algebra.mul(e,algebra.field.pow(x,k))
        syndrome.append(value)
    coefficients=[]
    for ell in range(len(syndrome)):
        value=0
        for k in range(ell+1,len(M)):value^=algebra.mul(M[k],syndrome[k-ell-1])
        coefficients.append(value)
    values=[];flags=[]
    for node in nodes:
        values.extend(algebra.jet(coefficients,node));flags.append(0)
    return values,flags


def block_data(algebra,nodes,offset,orders):
    A=[1];M=[1]
    slots=[]
    for k,g in enumerate(orders):
        node=nodes[offset+k]
        for _ in range(g):A=algebra.product(A,[node,1])
        M=algebra.product(M,[algebra.mul(node,node),0,1])
        slots.extend(2*(offset+k)+j for j in range(g,2))
    B=algebra.quotient(M,A)
    return A,B,slots


def extract(algebra,values,flags,nodes,max_g=None):
    blocks=[];offset=0;max_zero_order=0
    while offset<len(nodes):
        if all(values[2*j]==0 and flags[j]==0 for j in range(offset,len(nodes))):
            return blocks,offset,dict(status='terminal',max_zero_order=max_zero_order)
        orders=[];g=0
        while True:
            j=offset+len(orders)
            if j>=len(nodes):raise AssertionError(('insufficient constraints',offset,orders,values,flags))
            order=(2 if values[2*j+1]==0 else 1) if values[2*j]==0 and not flags[j] else 0
            orders.append(order);g+=order
            if max_g is not None and g>max_g:
                return blocks,offset,dict(status='lookahead_budget_exceeded',max_zero_order=max(max_zero_order,g))
            if len(orders)==g+1:break
        A,B,slots=block_data(algebra,nodes,offset,orders)
        constraints=[]
        for k,order in enumerate(orders):
            j=offset+k;node=nodes[j]
            if order==0:
                inverse=algebra.inverse_jet((values[2*j],values[2*j+1],flags[j]))
                assert not inverse[2]
                jet=algebra.scale_jet(inverse,A,node)
                constraints.extend([(node,0,jet[0]),(node,1,jet[1])])
            elif order==1:
                A1=algebra.quotient(A,[node,1])
                constraints.append((node,0,algebra.mul(algebra.evaluate_polynomial(A1,node),algebra.inv(values[2*j+1]))))
        P=algebra.interpolate(constraints)
        assert len(P)==g+2 and len(slots)==len(P)
        for j in range(offset,offset+len(orders)):
            values[2*j]=values[2*j+1]=0;flags[j]=0
        for slot,value in zip(slots,P):values[slot]=value
        end=offset+len(orders)
        for j in range(end,len(nodes)):
            jet=algebra.inverse_jet((values[2*j],values[2*j+1],flags[j]))
            jet=algebra.scale_jet(jet,A,nodes[j])
            jet=algebra.translate(jet,P,nodes[j])
            jet=algebra.divide_jet(jet,B,nodes[j])
            values[2*j:2*j+2]=jet[:2];flags[j]=jet[2]
        blocks.append(dict(offset=offset,orders=orders))
        max_zero_order=max(max_zero_order,g);offset=end
    return blocks,offset,dict(status='terminal',max_zero_order=max_zero_order)


def reconstruct(algebra,values,flags,nodes,blocks,terminal):
    N,D=[0],[1]
    for j in range(terminal,len(nodes)):
        assert values[2*j]==0 and flags[j]==0
        if values[2*j+1]:D=algebra.product(D,[nodes[j],1])
    for block in reversed(blocks):
        A,B,slots=block_data(algebra,nodes,block['offset'],block['orders'])
        P=[values[j] for j in slots]
        N,D=algebra.product(A,D),algebra.add(algebra.product(P,D),algebra.product(B,N))
    normalization=algebra.inv(D[-1])
    return ([algebra.mul(x,normalization) for x in N],
            [algebra.mul(x,normalization) for x in D])


def restore(algebra,values,flags,nodes,blocks):
    for block in reversed(blocks):
        offset,orders=block['offset'],block['orders']
        A,B,slots=block_data(algebra,nodes,offset,orders)
        P=[values[j] for j in slots]
        for j in range(offset+len(orders),len(nodes)):
            jet=algebra.scale_jet((values[2*j],values[2*j+1],flags[j]),B,nodes[j])
            jet=algebra.translate(jet,P,nodes[j])
            jet=algebra.inverse_jet(jet)
            jet=algebra.scale_jet(jet,A,nodes[j])
            values[2*j:2*j+2]=jet[:2];flags[j]=jet[2]
        restored=[]
        for k,order in enumerate(orders):
            node=nodes[offset+k]
            if order==0:
                u,v=algebra.jet(P,node)
                jet=algebra.scale_jet(algebra.inverse_jet((u,v,0)),A,node)
            elif order==1:
                A1=algebra.quotient(A,[node,1])
                jet=(0,algebra.mul(algebra.evaluate_polynomial(A1,node),algebra.inv(algebra.evaluate_polynomial(P,node))),0)
            else:jet=(0,0,0)
            restored.append(jet)
        for k,jet in enumerate(restored):
            j=offset+k;values[2*j:2*j+2]=jet[:2];flags[j]=jet[2]


def check_case(algebra,errors,nodes,M,max_g=None):
    values,flags=from_errors(algebra,errors,nodes,M)
    original=values[:]
    blocks,terminal,report=extract(algebra,values,flags,nodes,max_g)
    if report['status']=='terminal':
        N,D=reconstruct(algebra,values,flags,nodes,blocks,terminal)
        locator=[1]
        for x,e in errors:locator=algebra.product(locator,[x,1])
        assert D==locator,(errors,blocks,terminal,N,D,locator,values,flags)
        for x,e in errors:
            derivative=algebra.jet(locator,x)[1]
            expected=algebra.mul(algebra.mul(e,x),algebra.mul(algebra.evaluate_polynomial(M,x),derivative))
            assert algebra.evaluate_polynomial(N,x)==expected
    restore(algebra,values,flags,nodes,blocks)
    assert values==original and not any(flags)
    return report


def run_checks(exhaustive=False,destination=None):
    start=time.monotonic();algebra=Algebra(3);nodes=list(range(4));M=modulus(algebra,nodes)
    rng=random.Random(2026110812);cases=0;orders={};collisions=0
    if exhaustive:
        iterator=(list(zip(support,amps)) for w in range(5)
                  for support in itertools.combinations(range(1,8),w)
                  for amps in itertools.product(range(1,8),repeat=w))
    else:
        iterator=([ (x,rng.randrange(1,8)) for x in rng.sample(range(1,8),w)]
                  for w in range(5) for _ in range(100))
    for errors in iterator:
        report=check_case(algebra,errors,nodes,M)
        cases+=1;g=report['max_zero_order'];orders[g]=orders.get(g,0)+1
        collisions+=int(any(x in nodes for x,e in errors))
    result=dict(status='PASS_classical_confluent_reference_only',failures=0,cases=cases,
                exhaustive=exhaustive,max_zero_order_histogram=orders,node_collision_cases=collisions,
                elapsed_seconds=round(time.monotonic()-start,3),
                limitations='Block metadata, projective flags and residue-preserving synthesis are not quantum implementations.')
    if destination:destination.write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    print(json.dumps(run_checks('--exhaustive' in sys.argv,
                    Path(__file__).resolve().parents[1]/'logs'/'confluent.json'),indent=2))
