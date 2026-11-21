# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0
# Credits: Opus and Astra.
"""Explicitly bound compact Q48 endpoint; unchanged pinned04 phase angles."""
from contextlib import contextmanager
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
import hashlib,json

HERE=Path(__file__).resolve().parent;NARROW=HERE.parents[1]
SOURCE_PINS={
 'PAPER_GATE_RECEIPT_018_VARIANT.json':'99ef9a891d4e99b262b1a452ea48b18c536e91e7017f018b77bc37f1793ccffd',
 'native/candidate05/variant.py':'dc522e0881a15e7fbe99190df36d2bdbfd2b7c5438c3cd18f25d6537fecd5935',
 'native/candidate04/variant.py':'da023f7bc56995b9a8764a35c25b782f579b46e5a663e5b7100690819513e7ce',
 'native/candidate01/divider.py':'d0dbaf6fe4227da988c9cb9e9dee847624992c7c5cce7ab347990d5b0a116c05',
 'research/postgate_angle_refit/quantize50.json':'8670515091475959ab0edeae03cb736cdb1cb66cd7768366e69fafb7eff8bf72',
 'research/postgate_route_constants/offsets.json':'14f887ede91c2630fd3eca8386a7ac8b55a4951087bbdec009f1e1aee3414a99',
 'research/stream_phase/alias_ring/phase_ledger.py':'e8cc5a9095fd4bf29b5e77c6b58382b54ea46918102dbc10d1cad7c1edb255c3',
 'research/stream_phase/alias_ring/phase_ledger.json':'88bd82007c9ce6413d0c9aa8dae65184c1322f7025e9a23c0f57534f31dc63ec',
 'checkpoint002/cleanroom/baseline_stage97/engine/quadratic_terms.py':'3cf00a5af4227daee8c7d93102bc04ec4c2f25da3662e140069494d6f93f63ef',
 'checkpoint002/cleanroom/baseline_stage97/engine/cyclic_phase.py':'ee2619af8e8d9ef09230d1c29a73e5ca13112d6295dd13b1e9e6c03cc83316b8',
}
BINDING=None
LAST_PROXY_RECORDS=[]
LAST_PHASE_TRACE=[]


def verify_source_pins():
    for name,digest in SOURCE_PINS.items():
        assert hashlib.sha256((NARROW/name).read_bytes()).hexdigest()==digest,name
    gate=json.loads((NARROW/'PAPER_GATE_RECEIPT_018_VARIANT.json').read_text())
    assert gate['native_build_authorized'] and gate['Q']==48 and gate['expected_Toffolis']==1591
    assert gate['T']==4 and gate['R']==34 and gate['exact_margin_units64']==124372027
    assert hashlib.sha256((NARROW/gate['paper_gate_path']).read_bytes()).hexdigest()==gate['paper_gate_sha256']
    return gate


def compact_terms(original_terms):
    """Substitute c=f1*f3 before compilation AND before HMR phase repayment."""
    terms=tuple(10 if term==32 else term for term in original_terms)
    assert all(0<=term<32 and term.bit_count()<=2 for term in terms)
    return terms


@contextmanager
def threshold(builder,variables,t):
    assert BINDING is not None and len(variables)==5
    d=BINDING.divider;terms=compact_terms(d.THRESHOLDS[t])
    if max(term.bit_count() for term in terms)<=1:
        with d._affine_control(builder,variables,terms) as control:yield control
    else:
        control=builder.alloc_qubits(1)[0]
        d.xor_polynomial(builder,variables,control,terms)
        try:yield control
        finally:d._erase_polynomial(builder,control,variables,terms)


def raw_phase_endpoint(builder,token):
    """145 Toffolis,4T,34R at48 owners; raw angles are the old37-unit ones."""
    assert BINDING is not None;d=BINDING.divider
    v,u,flags=token.v,token.u,token.flags
    assert len(v)==12 and len(u)==14 and len(flags)==4
    assert builder.num_allocated_qubits==43
    d._sigma25_frame(builder,v,u)
    for q in u[:9]:builder.cx(v[0],q)
    builder.cx(v[1],u[9])
    signs={**token.history,25:u[10],26:u[9],36:u[13]}
    signs.update({j:u[35-j] for j in range(27,36)})
    assert sorted(signs)==list(range(12,37))
    for q in signs.values():builder.x(q)
    ones=list(builder.alloc_qubits(2));builder.x(d.array(ones))
    word=[ones[0]]+[signs[37-i] for i in range(1,26)]+[ones[1]]
    assert len(set(word))==27 and u[11] not in word and u[12] not in word
    p=builder.alloc_qubits(1)[0];d.xor_polynomial(builder,flags,p,(6,10))
    variables=flags+[p]
    assert builder.num_allocated_qubits==46
    assert d._route is BINDING.previous05.route and tuple(d.CENTRES)==(-1,-3,-7,-1,-2)
    d._route(builder,word,variables)
    slots=[word[i] for i in d._slots()]
    factor=1<<27
    for i,q in enumerate(slots):
        units=(1<<i)+(factor if i==0 else 0)
        builder.z_pow(q,Fraction(2*units,1<<37))
    for j in range(10):
        angle=Fraction(factor*(1<<j),1<<37)
        if j==0:
            with threshold(builder,variables,1) as q:
                builder.x(q);builder.z_pow(q,-2*angle);builder.x(q)
        elif j==9:
            assert angle==Fraction(1,2)
            builder.cz(flags[1],flags[3])
        else:
            with threshold(builder,variables,j+1) as q:d._feature(builder,q,slots[j],angle)
    d._route(builder,word,variables,inverse=True)
    d._erase_polynomial(builder,p,flags,(6,10))
    builder.x(d.array(ones));builder.free(d.array(ones))
    for q in signs.values():builder.x(q)
    builder.cx(v[1],u[9])
    for q in u[:9]:builder.cx(v[0],q)
    d._sigma25_frame(builder,v,u,inverse=True)
    assert builder.num_allocated_qubits==43


def phase_endpoint(builder,token):
    assert BINDING is not None
    proxy=BINDING.Proxy(builder)
    raw_phase_endpoint(proxy,token)
    LAST_PROXY_RECORDS.clear();LAST_PROXY_RECORDS.extend(proxy.finish())
    LAST_PHASE_TRACE.clear();LAST_PHASE_TRACE.extend(proxy.allocations)
    LAST_PHASE_TRACE.append(dict(event='complete',entry_owners=43,exit_owners=builder.num_allocated_qubits,
        observed_peak_owners=proxy.peak,generic_calls=proxy.generic,T_calls=proxy.T,direct_Clifford_Z_POW_calls=proxy.Clifford,
        last_overflow_implemented_as='CZ(flags1,flags3)',retained_controls=['p'],expected_Toffolis=145))


def install(previous05):
    """Bind only after the parent has installed the pinned candidate05 module."""
    global BINDING
    verify_source_pins()
    assert Path(previous05.__file__).resolve()==(NARROW/'native/candidate05/variant.py').resolve()
    previous05.verify_inputs();previous05.checked_quantized()
    d=previous05.divider;prior04=previous05.previous
    assert d._route is previous05.route and tuple(d.CENTRES)==(-1,-3,-7,-1,-2)
    assert d._slots()==previous05.ORIGINAL_SLOTS
    if BINDING is not None:
        assert BINDING.previous05 is previous05 and d.phase_endpoint is phase_endpoint
        return d
    assert d.phase_endpoint is prior04.phase_endpoint,'Unexpected phase replacement before compact binding.'
    class CompactAngleProxy(prior04.AngleProxy):
        def __init__(self,builder):
            super().__init__(builder);self.peak=builder.num_allocated_qubits;self.allocations=[]
            assert self.peak==43
        def alloc_qubits(self,count):
            result=self.builder.alloc_qubits(count);self.peak=max(self.peak,self.builder.num_allocated_qubits)
            self.allocations.append(dict(event='allocate',count=count,owners=self.builder.num_allocated_qubits,wires=list(map(str,result))))
            assert self.builder.num_allocated_qubits<=48,'Unpriced compact phase owner'
            return result
        def finish(self):
            # The last old Clifford Z_POW is deliberately a CZ now. No
            # direct Clifford rotation is allowed to disappear unaccounted.
            assert(self.generic,self.T,self.Clifford)==(34,4,0),(self.generic,self.T,self.Clifford)
            assert self.peak==48 and self.builder.num_allocated_qubits==43
            return self.records
    BINDING=SimpleNamespace(previous05=previous05,divider=d,Proxy=CompactAngleProxy)
    d.phase_endpoint=phase_endpoint
    return d
