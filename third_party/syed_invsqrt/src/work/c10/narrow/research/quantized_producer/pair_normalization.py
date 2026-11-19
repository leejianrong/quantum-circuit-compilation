#!/usr/bin/env python3
# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0
# Credits: Opus and Astra.
"""Direct pair normalization, exact Boolean/phase certificate and paper count.

No CircuitBuilder is instantiated. The proof packs every22-bit basis input
into Python integer truth vectors and checks all valid inputs simultaneously.
Every HMR outcome remains an independent symbolic phase coefficient.
"""
from pathlib import Path
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import sys,json,hashlib,resource,time
resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
HERE=Path(__file__).resolve().parent;NARROW=HERE.parents[1]
sys.path.insert(0,str(NARROW/'research/stream_phase'))
from drive_paper_ledger import PaperCounter,km
import codebook as cb
from stage94_bit_routing_math import operations,certificate as route_certificate
from thermometer_cleanup import binary_to_thermometer
from fusion.compiler import anf_from_truth
from dataclasses import asdict

MAX_X=3*(2**10-2)**2
COUNT_FULL=(1<<11)-1
COUNT_RAW=cb.word_functions(range(11),4)
COUNT_G=COUNT_RAW[0]&COUNT_RAW[1]
COUNT_BOOK=cb.Codebook(COUNT_RAW+[COUNT_G],size=11)
THRESHOLD_PLANS=[]
for j in range(1,11):
    t=sum(int(k>=j)<<k for k in range(11));expr=COUNT_BOOK.span.solve(t)
    assert expr is not None
    p=COUNT_BOOK.decode_expression(expr)
    assert p.evaluate_functions(COUNT_RAW+[COUNT_G],COUNT_FULL)==t
    THRESHOLD_PLANS.append(p)


def small_plan(n,fn):
    terms=anf_from_truth(tuple(fn(*[(x>>i)&1 for i in range(n)]) for x in range(1<<n)))
    assert all(t.bit_count()<=2 for t in terms)
    linear=sum(t for t in terms if t.bit_count()==1)
    edges=tuple(tuple(i for i in range(n)if t>>i&1)for t in terms if t.bit_count()==2)
    return cb.QuadraticCodePlan(n,0 in terms,linear,edges,(),linear)


ODD_FIRST=small_plan(2,lambda t1,h:1^h^(h&t1))
ODD_OTHER=small_plan(3,lambda prev,cur,h:prev^(h&(prev^cur)))


def route(builder,x,T,inverse=False):
    seq=list(operations(11))
    if inverse:seq.reverse()
    swaps=0
    for operation in seq:
        # k<=10. T11 is identicallyzero and never needs an owner.
        terms=[i for i in operation['prefix_terms'] if i<=10]
        assert terms and 0 not in terms
        control=T[terms[0]-1];others=[T[i-1]for i in terms[1:]]
        for q in others:builder.cx(q,control)
        for lane in range(2):
            builder.cswap(control,x[2*operation['first']+lane],x[2*operation['second']+lane]);swaps+=1
        for q in reversed(others):builder.cx(q,control)
    assert swaps==34


def forward(builder,x,flags):
    x=list(x);flags=list(flags)
    assert len(x)==22 and len(flags)==4
    P=[]
    for length in range(1,21):
        q=builder.alloc_qubits(1)[0]
        data=x[22-length]
        if length==1:
            builder.x(q);builder.cx(data,q)
        elif length==2:
            # Original task promise excludes both highest bits being1.
            builder.cx(P[-1],q);builder.cx(data,q)
        else:
            builder.x(data);builder.ccx(P[-1],data,q);builder.x(data)
        P.append(q)
    T=P[1::2]
    for bit,flag in enumerate(flags):
        for j in range(1<<bit,11,1<<bit):builder.cx(T[j-1],flag)
    route(builder,x,T)
    for j in range(1,11):
        q=P[2*j-2];m=builder.alloc_bits(1)[0];builder.hmr(q,m)
        if j==1:cb.emit_phase(builder,[T[0],x[21]],m,ODD_FIRST)
        else:cb.emit_phase(builder,[T[j-2],T[j-1],x[21]],m,ODD_OTHER)
        builder.free(m);builder.free(q)
    g=builder.alloc_qubits(1)[0];builder.ccx(flags[0],flags[1],g)
    for q,p in zip(T,THRESHOLD_PLANS):
        m=builder.alloc_bits(1)[0];builder.hmr(q,m);cb.emit_phase(builder,flags+[g],m,p)
        builder.free(m);builder.free(q)
    builder.del_and(flags[0],flags[1],g);builder.free(g)


def inverse(builder,x,flags):
    x=list(x);flags=list(flags)
    T,helpers=binary_to_thermometer(builder,flags,10)
    route(builder,x,T,inverse=True)
    for j in reversed(range(1,11)):
        q=T[j-1];a=x[22-2*j];bb=x[23-2*j]
        m=builder.alloc_bits(1)[0];builder.hmr(q,m)
        if j==1:builder.z(m)
        builder.push_condition(m)
        if j==1:
            builder.z(a);builder.z(bb);builder.cz(a,bb)
        else:
            prev=T[j-2]
            builder.z(prev);builder.cz(prev,a);builder.cz(prev,bb);builder.ccz(prev,a,bb)
        builder.pop_condition();builder.free(m)
    builder.free(km.array(helpers))


class Counter(PaperCounter):
    def swap(self,*args):pass


class TruthPhaseBuilder(Counter):
    """Truth-vector data and independent linear HMR phase symbols."""
    def __init__(self,cap,full,valid):
        super().__init__(cap);self.full=full;self.valid=valid;self.values={};self.phases={};self.measurements=0
    def alloc_qubits(self,n):
        out=super().alloc_qubits(n)
        for q in out:self.values[q]=0
        return out
    def value(self,q):
        if q is True:return self.full
        if q is False:return 0
        assert isinstance(q,km.q)
        return self.values[q]
    def free(self,x):
        if isinstance(x,km.q):assert not(self.value(x)&self.valid),('dirty_free',str(x))
        return super().free(x)
    def x(self,q):
        assert not self.stack and isinstance(q,km.q);self.values[q]^=self.full
    def cx(self,a,t):
        assert not self.stack and isinstance(t,km.q);self.values[t]^=self.value(a)
    def ccx(self,a,b,t):
        assert not self.stack;self._charge();self.values[t]^=self.value(a)&self.value(b)
    def swap(self,a,b):self.values[a],self.values[b]=self.values[b],self.values[a]
    def cswap(self,c,a,b):
        assert not self.stack;self._charge();delta=self.value(c)&(self.value(a)^self.value(b));self.values[a]^=delta;self.values[b]^=delta
    def _phase(self,value,extra=None):
        active=list(self.stack)
        if extra is not None:active.append(extra)
        assert len(set(active))<=1,('nonlinear_measurement_phase_not_supported',active)
        key=active[0] if active else None
        self.phases[key]=self.phases.get(key,0)^value
    def z(self,q):
        if isinstance(q,km.b):self._phase(self.full,extra=q)
        else:self._phase(self.value(q))
    def cz(self,a,b):self._phase(self.value(a)&self.value(b))
    def ccz(self,a,b,c):self._charge();self._phase(self.value(a)&self.value(b)&self.value(c))
    def hmr(self,q,m):
        assert not self.stack
        self.phases[m]=self.phases.get(m,0)^self.value(q);self.values[q]=0;self.measurements+=1
    def del_and(self,a,b,t):
        assert self.value(t)&self.valid==(self.value(a)&self.value(b)&self.valid)
        m=self.alloc_bits(1)[0];self.hmr(t,m);self.push_condition(m);self.cz(a,b);self.pop_condition();self.free(m)
    def check_phase(self):
        assert all(not(v&self.valid) for v in self.phases.values()),'unpaid_measurement_phase'


def input_truths():
    nbytes=1<<19;rows=[]
    for i in range(22):
        if i<3:data=bytes([0xaa if i==0 else 0xcc if i==1 else 0xf0])*nbytes
        else:
            length=1<<(i-3);data=(bytes(length)+bytes([255])*length)*(nbytes//(2*length))
        rows.append(int.from_bytes(data,'little'))
    return rows


def certify():
    start=time.monotonic();size=1<<22;full=(1<<size)-1;valid=(1<<(MAX_X+1))-2
    src=input_truths();b=TruthPhaseBuilder(49,full,valid);x=list(b.alloc_qubits(22));flags=list(b.alloc_qubits(4))
    for q,v in zip(x,src):b.values[q]=v
    expected=[0]*22;expected_flags=[0]*4
    for k in range(11):
        lo=1<<(20-2*k);hi=min(MAX_X+1,1<<(22-2*k));mask=((1<<hi)-(1<<lo)) if hi>lo else 0
        for i in range(2*k,22):expected[i]^=mask&src[i-2*k]
        for bit in range(4):
            if k>>bit&1:expected_flags[bit]^=mask
    forward(b,x,flags)
    assert all((b.value(q)^v)&valid==0 for q,v in zip(x,expected)),'wrong_pair_normalization'
    assert all((b.value(q)^v)&valid==0 for q,v in zip(flags,expected_flags)),'wrong_pair_count'
    assert b.num_allocated_qubits==26;b.check_phase();f=float(b.count);fpeak=b.peak;fm=b.measurements
    inverse(b,x,flags)
    assert all((b.value(q)^v)&valid==0 for q,v in zip(x,src)),'input_not_restored'
    assert all(b.value(q)&valid==0 for q in flags),'count_not_cleared'
    assert b.num_allocated_qubits==26;b.check_phase();total=float(b.count)
    assert (f,total)==(53,97.5),(f,total)
    return dict(status='EXACT_ALL_INPUT_AND_ALL_HMR_PHASE_CERTIFICATE_NOT_NATIVE',
        original_inputs=MAX_X,truth_vector_domain_bits=22,required_interval=[1,MAX_X],
        normalized_map='n=x*4**k, k=floor((22-bit_length(x))/2), n in[2^20,2^22)',
        mathematical_phase_error=0,all_original_bits_restored=True,all_scratch_and_flags_zero=True,
        forward_measurements=fm,total_independent_HMR_symbols=b.measurements,
        phase_proof='Every HMR outcome is an independent symbolic coefficient; each complete coefficient truth vector vanishes on every official input.',
        forward_E=f,inverse_expected_E=total-f,total_expected_E=total,peak=fpeak,T=0,R=0,
        seconds=time.monotonic()-start,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


def paper(cap):
    b=Counter(cap);x=list(b.alloc_qubits(22));flags=list(b.alloc_qubits(4));forward(b,x,flags)
    f=float(b.count);fp=b.peak;assert b.num_allocated_qubits==26;b.peak=26
    inverse(b,x,flags);assert b.num_allocated_qubits==26
    return dict(Q_cap=cap,forward_E=f,inverse_expected_E=float(b.count)-f,total_expected_E=float(b.count),
                forward_peak=fp,inverse_peak=b.peak,T=0,R=0)


def main():
    result=dict(scope='NEW_PAIR_NORMALIZATION_PAPER_AND_EXACT_BOOLEAN_ONLY',
        route=route_certificate(11),threshold_plans=[asdict(p)for p in THRESHOLD_PLANS],
        certificate=certify(),paper=[paper(q)for q in range(46,53)],
        excluded_transfer='The122E Stage94 semilog/packed interface is not used.',
        native_gate='Use only after the full actual lifecycle ledger is updated and clears its paper gate; native proof still required.')
    (HERE/'pair_normalization.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'certificate':result['certificate'],'paper':result['paper']},indent=2))

if __name__=='__main__':main()
