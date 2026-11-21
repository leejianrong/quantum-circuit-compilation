# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0
# Credits: Opus and Astra.
"""Authorized26-ring endpoint, explicit new angles and complete local cleanup."""
from pathlib import Path
from fractions import Fraction
from types import SimpleNamespace
import hashlib,json

HERE=Path(__file__).resolve().parent;NARROW=HERE.parents[1]
MODULUS=1<<50
CENTRES=(0,-2,-6,0,-1)
SITES=tuple(f'base_i{i}'for i in range(26))+tuple(f'overflow_j{j}'for j in range(7))+('global_one',)
PINS={
 'PAPER_GATE_RECEIPT_022_VARIANT.json':'f8cfe4331b37a5184a4aab17ee85b4ac892c08c2cfb863fc4b1c1b3c9978262e',
 'research/combined_q48_ring26/COMPLETE_GATE.json':'49ce6e7007b19abcd533b82a9f291b617cbc1c864a3d66287c0e63a87ebb82c4',
 'research/ring26_phase/COMPLETE_GATE_RING26_ZERO33.json':'b579924175ee8e73c61c2f945b2d85e8ba2e536a8dbd8288a8332628142cd569',
 'research/ring26_phase/frozen/global_zero33.json':'c0eab1edd234e32d5baa1a51a0fec46abf82165d3973ffda825d2149f67f11e5',
 'research/ring26_phase/basis.json':'a3bacdd5ef8e16acb8560a40e60e2c998f8171973b1dcc062a47503c5218d744',
 'native/candidate01/divider.py':'d0dbaf6fe4227da988c9cb9e9dee847624992c7c5cce7ab347990d5b0a116c05',
 'native/candidate06/phase06.py':'4e979c47bc90317a6ac3576bc74964cf74222c2006e1630f6b17075af51ccdfb',
}
BINDING=None
LAST_ANGLE_RECORDS=[]
LAST_PHASE_TRACE=[]
ROUTE_TRACE=[]


def verify_sources():
    for name,digest in PINS.items():assert hashlib.sha256((NARROW/name).read_bytes()).hexdigest()==digest,name
    accepted=json.loads((NARROW/'PAPER_GATE_RECEIPT_022_VARIANT.json').read_text())
    assert accepted['native_build_authorized'] and (accepted['Q'],accepted['expected_Toffolis'],accepted['T'],accepted['R'])==(48,1584,4,33)
    return json.loads((NARROW/'research/ring26_phase/basis.json').read_text())


def angle_class(half_turns):
    angle=Fraction(half_turns)
    if angle%Fraction(1,2)==0:return 'Clifford'
    if angle%Fraction(1,4)==0:return 'T'
    return 'generic'


class Recorder:
    def __init__(self,builder):
        self.builder=builder;self.peak=builder.num_allocated_qubits
        self.generic=self.T=self.Clifford=0;self.site=None;self.fixed=None
        self.records=[];self.allocations=[];self.fixed_records=[]
        assert self.peak==43
    def __getattr__(self,name):return getattr(self.builder,name)
    def alloc_qubits(self,count):
        wires=self.builder.alloc_qubits(count);self.peak=max(self.peak,self.builder.num_allocated_qubits)
        self.allocations.append(dict(event='allocate',count=count,owners=self.builder.num_allocated_qubits,wires=list(map(str,wires))))
        assert self.builder.num_allocated_qubits<=48,'Unpriced ring26 endpoint owner'
        return wires
    def z_pow(self,target,half_turns):
        value=Fraction(half_turns);kind=angle_class(value)
        if kind=='generic':
            assert self.site is not None and self.fixed is None
            i=self.site;assert i==len(self.records) and i<33
            assert value==Fraction(2*BINDING.angles[i],MODULUS)
            self.records.append(dict(index=i,site=SITES[i],target=str(target),new_half_turns=str(value),
                turn_units50=BINDING.angles[i],angle_class=kind,emitted=True))
            self.generic+=1
        elif kind=='T':
            assert self.site is None and self.fixed in('overflow_j7','overflow_j8')
            self.T+=1;self.fixed_records.append(dict(site=self.fixed,half_turns=str(value),target=str(target),kind='T'))
        else:
            assert self.site is None and self.fixed=='overflow_j9' and value==1
            self.Clifford+=1;self.fixed_records.append(dict(site=self.fixed,half_turns=str(value),target=str(target),kind='Clifford'))
        return self.builder.z_pow(target,value)
    def finish(self):
        assert(self.generic,self.T,self.Clifford)==(33,4,1)
        assert self.site is None and self.fixed is None
        assert len(self.records)==34 and self.records[-1]['site']=='global_one' and not self.records[-1]['emitted']
        assert self.peak==48 and self.builder.num_allocated_qubits==43
        assert len(self.fixed_records)==5
        return self.records


def route26(builder,word,variables,inverse=False):
    """Original centres modulo26, no candidate05 omitted pair."""
    d=BINDING.divider
    assert len(word)==26 and len(set(word))==26 and len(variables)==6
    stages=list(range(5));gates=[];counts=[]
    if inverse:stages.reverse()
    for stage in stages:
        count=0
        with d._affine_control(builder,variables,d.CONTROLS[stage])as control:
            for i in range(26):
                j=(CENTRES[stage]-i)%26
                if i<j:
                    builder.cswap(control,word[i],word[j]);count+=1
                    gates.append(dict(stage=stage,positions=[i,j],arguments=list(map(str,(control,word[i],word[j])))))
        counts.append(dict(stage=stage,swaps=count))
    assert len(gates)==61 and sorted((row['stage'],row['swaps'])for row in counts)==[(0,12),(1,12),(2,12),(3,12),(4,13)]
    ROUTE_TRACE.append(dict(inverse=inverse,ring_bits=26,centres=list(CENTRES),omissions=[],swap_count=61,stages=counts,gates=gates))


def raw_phase_endpoint(builder,token):
    d=BINDING.divider;v,u,flags=token.v,token.u,token.flags
    assert(len(v),len(u),len(flags))==(12,14,4) and builder.num_allocated_qubits==43
    d._sigma25_frame(builder,v,u)
    for q in u[:9]:builder.cx(v[0],q)
    builder.cx(v[1],u[9])
    signs={**token.history,25:u[10],26:u[9],36:u[13]}
    signs.update({j:u[35-j]for j in range(27,36)})
    assert sorted(signs)==list(range(12,37))
    for q in signs.values():builder.x(q)
    one=builder.alloc_qubits(1)[0];builder.x(one)
    word=[signs[36-i]for i in range(25)]+[one]
    assert len(set(word))==26 and u[11]not in word and u[12]not in word
    p=builder.alloc_qubits(1)[0];d.xor_polynomial(builder,flags,p,(6,10))
    c=builder.alloc_qubits(1)[0];d.xor_polynomial(builder,flags,c,(10,))
    variables=flags+[p,c];assert builder.num_allocated_qubits==46
    route26(builder,word,variables)
    slots=[word[i]for i in BINDING.slots]
    for i,q in enumerate(slots):
        builder.site=i;builder.z_pow(q,Fraction(2*BINDING.angles[i],MODULUS));builder.site=None
    for j in range(10):
        if j==9:
            builder.fixed='overflow_j9';builder.z_pow(c,Fraction(1));builder.fixed=None
        elif j<=6:
            with d._threshold(builder,variables,j+1)as control:
                builder.site=26+j
                d._feature(builder,control,slots[j],Fraction(BINDING.angles[26+j],MODULUS))
                builder.site=None
        else:
            with d._threshold(builder,variables,j+1)as control:
                builder.fixed=f'overflow_j{j}'
                d._feature(builder,control,slots[j],Fraction(1,8)if j==7 else Fraction(1,4))
                builder.fixed=None
    route26(builder,word,variables,inverse=True)
    # The explicit topone has returned. The accepted global angle is exactly
    # identity; record the checked site without emitting a spurious rotation.
    assert BINDING.angles[33]==0 and len(builder.records)==33
    builder.records.append(dict(index=33,site='global_one',target=str(one),new_half_turns='0',
        turn_units50=0,angle_class='Clifford',emitted=False))
    d._erase_polynomial(builder,c,flags,(10,))
    d._erase_polynomial(builder,p,flags,(6,10))
    builder.x(one);builder.free(one)
    for q in signs.values():builder.x(q)
    builder.cx(v[1],u[9])
    for q in u[:9]:builder.cx(v[0],q)
    d._sigma25_frame(builder,v,u,inverse=True)
    assert builder.num_allocated_qubits==43


def phase_endpoint(builder,token):
    assert BINDING is not None
    proxy=Recorder(builder);ROUTE_TRACE.clear();raw_phase_endpoint(proxy,token)
    LAST_ANGLE_RECORDS.clear();LAST_ANGLE_RECORDS.extend(proxy.finish())
    LAST_PHASE_TRACE.clear();LAST_PHASE_TRACE.extend(proxy.allocations)
    LAST_PHASE_TRACE.append(dict(event='complete',entry_owners=43,exit_owners=builder.num_allocated_qubits,
        observed_peak_owners=proxy.peak,generic_calls=proxy.generic,T_calls=proxy.T,
        direct_Clifford_Z_POW_calls=proxy.Clifford,global_identity_validated_and_omitted=True,
        expected_Toffolis=139,local_HMR_functions=15,all_local_outcomes_repaid_before_exit=True,
        no_TableDebts_transfer=True,fixed_phase_records=proxy.fixed_records))


def install(previous06,accepted_angles,accepted_phase_gate):
    global BINDING
    basis=verify_sources();angles=tuple(accepted_angles)
    assert Path(previous06.__file__).resolve()==(NARROW/'native/candidate06/variant.py').resolve()
    previous06.verify_inputs();d=previous06.divider
    assert list(angles)==accepted_phase_gate['new_angles_turn_units50']
    assert accepted_phase_gate['phase_expected_Toffolis']==139 and accepted_phase_gate['endpoint_peak']==48
    assert accepted_phase_gate['R']==33 and accepted_phase_gate['T']==4 and accepted_phase_gate['phase_entry_exit_owners']==43
    assert tuple(accepted_phase_gate['phase_site_order'])==SITES and len(angles)==34 and angles[-1]==0
    assert all(angle_class(Fraction(2*a,MODULUS))=='generic'for a in angles[:33])
    assert any(a&1 for a in angles[:33])
    if BINDING is not None:
        assert BINDING.previous06 is previous06 and BINDING.angles==angles and d.phase_endpoint is phase_endpoint
        return d
    assert d.phase_endpoint is previous06.local_module('phase06').phase_endpoint
    assert tuple(tuple(x)for x in basis['controls'])==tuple(d.CONTROLS)
    BINDING=SimpleNamespace(previous06=previous06,divider=d,angles=angles,slots=tuple(basis['slots']))
    d.phase_endpoint=phase_endpoint
    return d
