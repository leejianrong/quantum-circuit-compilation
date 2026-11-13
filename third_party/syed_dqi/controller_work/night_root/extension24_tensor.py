# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Fresh rank-99 tensor for F4096[t]/(t^2+t+delta).

Use a degree-six polynomial basis over GF16, eleven evaluations, and a
rank-nine GF16 product derived by two levels of quadratic Karatsuba.
No external implementation or literal extension multiplication tensor.
Classical only; importing this file does not load the quantum engine.
"""
from functools import cache
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'night_converter'))
from night_reference import F


def trace(a):
    out=0
    for _ in range(12):
        out ^= a
        a=F.square(a)
    assert out in (0,1)
    return out


DELTA=next(a for a in range(1,4096) if trace(a))


def mul(a,b):
    a0,a1=a&4095,a>>12
    b0,b1=b&4095,b>>12
    aa,bb=F.mul(a0,b0),F.mul(a1,b1)
    mixed=F.mul(a0^a1,b0^b1)
    return (aa ^ F.mul(DELTA,bb)) | ((mixed^aa)<<12)


def power(a,n):
    result=1
    while n:
        if n&1:result=mul(result,a)
        a=mul(a,a);n>>=1
    return result


def small_mul(a,b):
    out=0
    while b:
        if b&1:out^=a
        b>>=1;a<<=1
        if a&16:a^=0x13
    return out


def small_power(a,n):
    out=1
    while n:
        if n&1:out=small_mul(out,a)
        a=small_mul(a,a);n>>=1
    return out


def inverse_columns(columns):
    n=len(columns)
    rows=[sum(((c>>i)&1)<<j for j,c in enumerate(columns)) | (1<<(n+i)) for i in range(n)]
    for j in range(n):
        pivot=next((i for i in range(j,n) if rows[i]>>j&1),None)
        if pivot is None:raise ValueError('singular basis')
        rows[j],rows[pivot]=rows[pivot],rows[j]
        for i in range(n):
            if i!=j and rows[i]>>j&1:rows[i]^=rows[j]
    return tuple(row>>n for row in rows)


def apply(rows,value):
    return sum(((r&value).bit_count()&1)<<j for j,r in enumerate(rows))


def compose(mask,rows):
    out=0
    for j,row in enumerate(rows):
        if mask>>j&1:out^=row
    return out


def interpolate_matrix(n):
    rows=[[small_power(a,k) for k in range(n)]+[int(a==k) for k in range(n)] for a in range(n)]
    for j in range(n):
        i=next(i for i in range(j,n) if rows[i][j])
        rows[j],rows[i]=rows[i],rows[j]
        inv=small_power(rows[j][j],14)
        rows[j]=[small_mul(v,inv) for v in rows[j]]
        for i in range(n):
            if i!=j and rows[i][j]:
                factor=rows[i][j]
                rows[i]=[a^small_mul(factor,b) for a,b in zip(rows[i],rows[j])]
    return [r[n:] for r in rows]


@cache
def small_tensor():
    beta=next(a for a in range(2,16) if small_mul(a,a)^a^1==0)
    embed=lambda a:(a&1)^((a>>1)*beta)
    theta=next(a for a in range(2,16) if small_mul(a,a)^a^beta==0)
    columns=[1,beta,theta,small_mul(theta,beta)]
    rows=inverse_columns(columns)
    base=((1,1,3),(2,2,1),(3,3,2))
    terms=[]
    for kind,weight in ((0,1^theta),(1,beta),(2,theta)):
        chosen=rows[:2] if kind==0 else rows[2:] if kind==1 else tuple(a^b for a,b in zip(rows[:2],rows[2:]))
        for left,right,out in base:
            terms.append((compose(left,chosen),compose(right,chosen),small_mul(weight,embed(out))))
    assert len(terms)==9
    for a in range(16):
        for b in range(16):assert tensor_value(terms,a,b)==small_mul(a,b)
    return tuple(terms)


def tensor_value(terms,a,b):
    out=0
    for left,right,weight in terms:
        if (left&a).bit_count()&1 and (right&b).bit_count()&1:out^=weight
    return out


@cache
def basis():
    beta=next(a for a in range(2,4096) if F.square(F.square(a))^a^1==0)
    sub=[1,beta,F.square(beta),F.mul(F.square(beta),beta)]
    def embed(a):
        out=0
        for j,w in enumerate(sub):
            if a>>j&1:out^=w
        return out
    for small in range(4096):
        theta=(1<<12)^small
        columns=[mul(power(theta,i),w) for i in range(6) for w in sub]
        try:rows=inverse_columns(columns)
        except ValueError:continue
        return beta,theta,tuple(sub),rows
    raise AssertionError('no degree-six basis')


@cache
def multiplication_tensor():
    beta,theta,sub,rows=basis()
    def embed(a):
        out=0
        for j,w in enumerate(sub):
            if a>>j&1:out^=w
        return out
    interpolation=interpolate_matrix(11)
    terms=[]
    for point in range(11):
        eval_rows=[0]*4
        for j in range(24):
            tower=apply(rows,1<<j);value=0
            for i in range(6):value^=small_mul((tower>>(4*i))&15,small_power(point,i))
            for k in range(4):eval_rows[k]|=((value>>k)&1)<<j
        weight=0
        for k in range(11):weight^=mul(embed(interpolation[k][point]),power(theta,k))
        for left,right,out in small_tensor():
            terms.append((compose(left,eval_rows),compose(right,eval_rows),mul(weight,embed(out))))
    assert len(terms)==99 and all(a and b and c for a,b,c in terms)
    return tuple(terms)


if __name__=='__main__':
    import hashlib,json,random,time
    started=time.monotonic();terms=multiplication_tensor();rng=random.Random(202611112107)
    checks=0
    for i in range(24):
        for j in range(24):
            assert tensor_value(terms,1<<i,1<<j)==mul(1<<i,1<<j)
            checks+=1
    for _ in range(4096):
        a,b=rng.randrange(1<<24),rng.randrange(1<<24)
        assert tensor_value(terms,a,b)==mul(a,b)
        checks+=1
    beta,theta,sub,rows=basis()
    out=dict(status='PASS_EXACT_BILINEAR_TENSOR_CERTIFICATE',rank=len(terms),degree=24,
             tower_delta=DELTA,subfield16_generator=beta,degree6_generator=theta,
             exhaustive_bit_basis_pairs=576,random_pairs=4096,total_checks=checks,
             quantum_check=False,mean_T=None,Q=None,
             explanation='The576basis-pair checks certify every bilinear input pair; random checks are additional.',
             tensor_sha256=hashlib.sha256(json.dumps(terms,separators=(',',':')).encode()).hexdigest(),
             source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             elapsed_seconds=time.monotonic()-started)
    Path(__file__).with_name('extension24-tensor-report.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(out,indent=2))
