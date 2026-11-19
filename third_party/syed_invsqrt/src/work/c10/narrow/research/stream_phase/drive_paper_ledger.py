# Copyright 2026 Syed Asad Ali
# SPDX-License-Identifier: Apache-2.0
# Credits: Opus and Astra.
"""Source-expanded resource ledger, without constructing any native circuit.

This counter implements only allocation and gate accounting. It intentionally
has no finish_circuit method and produces no KMB. The arithmetic emitter's
existing deterministic segmentation/dirty-terminal policy supplies the paper
schedule. This is a cost calculation, not an arithmetic or native proof.
"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import sys,json,resource
from pathlib import Path
from fractions import Fraction
resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
HERE=Path(__file__).resolve().parent;NARROW=HERE.parents[1]
sys.path[:0]=[str(NARROW/'base/official/kickmix'),str(NARROW/'checkpoint002/cleanroom/baseline_stage97/engine')]
import kickmix as km
from paired_arithmetic import forward_add,inverse_add
from fusion.lookup import load_table


class PaperCounter:
    def __init__(self,cap):
        self.max_qubits=cap;self.live=set();self.nextq=0;self.nextb=0
        self.pool=[];self.stack=[];self.count=Fraction(0);self.peak=0
    @property
    def num_allocated_qubits(self):return len(self.live)
    def alloc_qubits(self,n):
        if len(self.live)+n>self.max_qubits:raise ValueError(f'paper allocation {len(self.live)}+{n}>{self.max_qubits}')
        out=[]
        for _ in range(n):
            if self.pool:q=self.pool.pop()
            else:q=km.q(self.nextq);self.nextq+=1
            self.live.add(q);out.append(q)
        self.peak=max(self.peak,len(self.live));return km.array(out)
    def alloc_bits(self,n):
        out=km.array([km.b(i) for i in range(self.nextb,self.nextb+n)]);self.nextb+=n;return out
    def free(self,x):
        if isinstance(x,km.q):
            assert x in self.live;self.live.remove(x);self.pool.append(x)
        elif isinstance(x,km.b):pass
        else:
            for q in x:self.free(q)
    def push_condition(self,b):self.stack.append(b)
    def pop_condition(self):self.stack.pop()
    def _charge(self,n=1):self.count+=Fraction(n,1<<len(set(self.stack)))
    def ccx(self,*a):self._charge()
    def ccz(self,*a):self._charge()
    def cswap(self,*a):self._charge()
    def cx(self,*a):pass
    def cz(self,*a):pass
    def x(self,*a):pass
    def z(self,*a):pass
    def hmr(self,*a):pass
    def del_and(self,*a):pass
    def bit_store(self,*a):pass


def paper(cap,m=37,schedule=None,mode='baseline'):
    schedule=schedule or {}
    b=PaperCounter(cap);v=list(b.alloc_qubits(12))
    p=list(b.alloc_qubits(10 if mode=='baseline' else 16))
    flags=list(b.alloc_qubits(4));u=list(b.alloc_qubits(14));original=list(u)
    base_data=b.num_allocated_qubits
    table=[(1<<(min(k,10)+3))-1 for k in range(16)]
    load_before=b.count;load_table(b,table,flags,u);load_forward=b.count-load_before
    # Early s=10 initializer correction is completed before this adder.
    # Its two temporary ANDs have already been erased; do not charge their
    # storage through the subsequent subtract-v pass.
    extra_init=0
    tmp=b.alloc_qubits(extra_init)
    init_before=b.count;init=forward_add(b,v,u);init_forward=b.count-init_before;b.free(tmp)
    records=[];rounds=[]
    for j in range(1,m-1):
        k=schedule.get(j,0);u=[u[-1]]+u[:-1]
        phase='outside'
        if mode!='baseline' and 1<=j<=24:
            phase='always' if 10<=j<=14 else 'masked'
        if phase=='always':helper_count=0 if mode=='cswap' else 1
        elif phase=='masked':helper_count=2 if mode=='cswap' else 3
        else:helper_count=0
        tmp=list(b.alloc_qubits(helper_count))
        carry=tmp[-1] if tmp else v[k]
        before=b.count;debt=forward_add(b,v[k+1:],u[k+1:],carry_in=carry)
        rounds.append(dict(j=j,k=k,phase=phase,helpers=helper_count,forward=float(b.count-before)))
        records.append((j,k,phase,helper_count,debt));b.free(tmp)
    for j,k,phase,helper_count,debt in reversed(records):
        tmp=list(b.alloc_qubits(helper_count));carry=tmp[-1] if tmp else v[k]
        before=b.count
        inverse_add(b,v[k+1:],u[k+1:],debt,carry_in=carry,dirty_wires=p+flags)
        rounds[j-1]['inverse']=float(b.count-before)
        b.free(tmp);u=u[1:]+u[:1]
    assert u==original
    tmp=b.alloc_qubits(extra_init);before=b.count
    inverse_add(b,v,u,init,dirty_wires=p+flags)
    init_inverse=b.count-before;b.free(tmp)
    before=b.count;load_table(b,table,flags,u);load_inverse=b.count-before
    arithmetic=b.count
    if mode=='baseline':routing=Fraction(0);routing_detail={}
    else:
        # 19 boundary updates and five always-active updates (j=0 is in init).
        # Every threshold gadget is measured after use; their combined debt is
        # a function of k only, with one half-probability cubic CCZ.
        carry_logic=2*(19*(3 if mode=='cswap' else 2)+5*(2 if mode=='cswap' else 1))
        routing_detail=dict(ring16_permutation=72,threshold_preparation=54,
            threshold_debt=0.5,carry_logic=carry_logic,initialization_correction=8)
        routing=sum(map(Fraction,routing_detail.values()))
    return dict(status='SOURCE_EXPANDED_PAPER_LEDGER_NOT_NATIVE',mode=mode,Q_cap=cap,
        data_registers={'root_v':12,'correction_with_zero_sentinel':len(p),'flags':4,'u':14},
        base_data=base_data,peak_allocation=b.peak,m=m,schedule=schedule,
        adder_and_lookup_toffolis=float(arithmetic),routing_toffolis=float(routing),
        expected_toffolis=float(arithmetic+routing),T=1,R=m-3,
        lookup_forward=float(load_forward),lookup_inverse=float(load_inverse),
        initial_add_forward=float(init_forward),initial_add_inverse=float(init_inverse),
        routing_detail=routing_detail,rounds=rounds)


def main():
    calibration=[]
    old=json.loads((NARROW/'checkpoint002/cleanroom/table_arch/taper_balanced_caps.json').read_text())
    schedule={j:j-26 for j in range(28,36)}
    for row in old['rows']:
        p=paper(row['Q'],37,schedule,'baseline')
        expected=row['counts']['toffoli_like']
        calibration.append(dict(Q=row['Q'],paper=p['expected_toffolis'],previous_native=expected,match=p['expected_toffolis']==expected))
    assert all(x['match'] for x in calibration),calibration
    rows=[]
    schedules=[(36,{},'m36_exact'),(36,{j:j-29 for j in range(30,35)},'m36_tight'),
               (37,schedule,'m37_balanced'),(37,{j:j-25 for j in range(27,36)},'m37_wide')]
    for cap in range(48,53):
        for mode in ('binary','cswap'):
            for m,sched,name in schedules:
                try:
                    p=paper(cap,m,sched,mode);p['schedule_name']=name;rows.append(p)
                except Exception as e:rows.append(dict(Q_cap=cap,mode=mode,schedule_name=name,status='PAPER_SCHEDULE_BLOCKED',reason=str(e)))
    result=dict(scope='Pure Python allocation/expected-gate counter expanding existing own arithmetic source. No native CircuitBuilder, KMB, simulator, or proof of the new arithmetic. Full producer, normalization, root and rotation charge remain separate line items.',
                calibration=calibration,rows=rows)
    (HERE/'drive_paper_ledger.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(calibration))
    for r in rows:print(json.dumps({k:v for k,v in r.items()if k not in ['rounds','schedule','routing_detail']}))

if __name__=='__main__':main()
