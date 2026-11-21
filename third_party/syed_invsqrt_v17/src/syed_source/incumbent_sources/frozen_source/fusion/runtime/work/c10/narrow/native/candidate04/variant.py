# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0
# Credits: Opus and Astra.
"""Isolated angle-only candidate04 on the pinned candidate03 arithmetic."""
from pathlib import Path
from fractions import Fraction
import copy, hashlib, importlib.util, json, math, os, sys

os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
HERE=Path(__file__).resolve().parent;NARROW=HERE.parents[1]
BASE=HERE.parent/'candidate01';RESEARCH=NARROW/'research/postgate_angle_refit'
INPUTS=json.loads((HERE/'INPUTS.json').read_text())


def verify_inputs():
    for pin in INPUTS['files']:
        raw=(NARROW/pin['path']).read_bytes()
        assert len(raw)==pin['bytes'] and hashlib.sha256(raw).hexdigest()==pin['sha256'],pin['path']


verify_inputs()
path=HERE.parent/'candidate03/variant.py'
spec=importlib.util.spec_from_file_location('candidate04_pinned_candidate03_variant',path)
previous=importlib.util.module_from_spec(spec);sys.modules[spec.name]=previous;spec.loader.exec_module(previous)
common=previous.common;divider=previous.previous.baseline_divider
BOUND=json.loads((RESEARCH/'quantize50_bound.json').read_text())
ACCEPTED=json.loads((NARROW/'PAPER_GATE_RECEIPT_014_VARIANT.json').read_text())
assert ACCEPTED['native_build_authorized'] and ACCEPTED['preserve_candidates_01_02_03']
assert hashlib.sha256((RESEARCH/'quantize50_bound.json').read_bytes()).hexdigest()==ACCEPTED['bound_file_sha256']
assert BOUND['proved_quantized_margin_lower_bound_units']==ACCEPTED['proved_margin_lower_bound_units64']==124286782
COEFFICIENTS37=tuple((1<<i)+((1<<27) if i==0 else 0) for i in range(27))+(-(1<<27),)+tuple(1<<(27+j) for j in range(1,7))
SITES=tuple(f'base_i{i}' for i in range(27))+('threshold_j0',)+tuple(f'overflow_j{j}' for j in range(1,7))
NEW_TURN_UNITS50=tuple(BOUND['new_generic_turn_units50'])
assert len(NEW_TURN_UNITS50)==len(COEFFICIENTS37)==len(SITES)==34
assert all(type(v) is int for v in NEW_TURN_UNITS50)
assert all(BOUND['delta_turn_units64']),'The literal34-change structural comparison requires all34 nonzero deltas.'
assert [r['site'] for r in BOUND['angle_sites']]==list(SITES)
ORIGINAL_ENDPOINT=divider.phase_endpoint
LAST_PROXY_RECORDS=[]
_INSTALLED=False


def angle_class(half_turns):
    angle=Fraction(half_turns)
    if (2*angle).denominator==1:return 'Clifford'
    if (4*angle).denominator==1:return 'T'
    return 'generic'


def checked_quantized():
    """Require the full exact scan; the conservative bound alone cannot emit."""
    path=RESEARCH/'quantize50.json';raw=path.read_bytes();result=json.loads(raw)
    assert result['status']=='EXACT_ALL_INPUT_QUANTIZE50_PAPER_PASS_NATIVE_PENDING'
    assert result['script_sha256']==hashlib.sha256((RESEARCH/'quantize50.py').read_bytes()).hexdigest()
    for relative,digest in result['source_pins'].items():
        assert hashlib.sha256((NARROW/relative).read_bytes()).hexdigest()==digest,relative
    assert result['inputs']==3133452 and result['original_tolerance_unchanged']
    assert result['accuracy_decision_uses_only_integer_arithmetic']
    assert result['new_generic_turn_units50']==list(NEW_TURN_UNITS50)
    assert result['delta_turn_units64']==BOUND['delta_turn_units64']
    assert result['new_generic_turn_units64']==BOUND['new_generic_turn_units64']
    assert result['maximum_generic_turn_denominator']==1<<50
    assert result['all_angle_classes_exactly_generic']
    assert result['fixed_T']==4 and result['fixed_R']==34 and result['Q']==49
    assert result['expected_Toffolis']==1562.5
    stats=result['exact_statistics']['quantized50']
    assert stats['inputs']==3133452 and stats['failures']==0
    assert stats['minimum_margin_units']>=ACCEPTED['proved_margin_lower_bound_units64']
    assert result['sum_absolute_angle_quantization_change_units']==110274
    assert result['rotation_charge']<=ACCEPTED['rotation_charge_upper_bound']+1e-12
    assert result['predicted_complete_cost']<=ACCEPTED['complete_cost_upper_bound']+1e-9
    assert len(result['angle_sites'])==34
    for site,old,new,row in zip(SITES,COEFFICIENTS37,NEW_TURN_UNITS50,result['angle_sites']):
        assert row['site']==site and row['turn_units50']==new
        assert Fraction(row['half_turns'])==Fraction(2*new,1<<50)
        assert angle_class(Fraction(2*old,1<<37))==angle_class(Fraction(2*new,1<<50))=='generic'
    return result,hashlib.sha256(raw).hexdigest()


def variant_gate():
    verify_inputs();result=copy.deepcopy(previous.variant_gate())
    quantized,digest=checked_quantized();primary=result['primary']
    primary['rotation_charge']=quantized['rotation_charge']
    primary['complete_components']['rotation_charge']=quantized['rotation_charge']
    primary['total_E']=quantized['predicted_complete_E']
    primary['paper_cost']=quantized['predicted_complete_cost']
    primary['quantized_exact_minimum_margin_units64']=quantized['exact_statistics']['quantized50']['minimum_margin_units']
    primary['proved_margin_lower_bound_units64']=ACCEPTED['proved_margin_lower_bound_units64']
    primary['phase_grid_turns']='1/1125899906842624'
    primary['margins']={name:limit-primary['paper_cost'] for name,limit in [('stage97',92278.95),('target',89987),('stretch',82740)]}
    assert primary['Toffolis_expected']==1562.5 and primary['T']==4 and primary['R']==34 and primary['Q']==49
    assert math.isclose(primary['total_E'],1562.5+1+primary['rotation_charge'],rel_tol=0,abs_tol=1e-10)
    result['status']='ACCEPTED_CANDIDATE04_FULL_DOMAIN_QUANTIZED_ANGLE_GATE_NATIVE_PENDING'
    result['candidate04_quantize50_sha256']=digest
    return result


class AngleProxy:
    """Intercept only exact z_pow angles; all allocation/data APIs delegate."""
    def __init__(self,builder):
        self.builder=builder;self.generic=0;self.T=0;self.Clifford=0;self.records=[]

    def __getattr__(self,name):return getattr(self.builder,name)

    def z_pow(self,target,half_turns):
        old=Fraction(half_turns);kind=angle_class(old)
        if kind=='generic':
            index=self.generic
            assert index<34,('unexpected_generic_rotation',index,str(old))
            expected=Fraction(2*COEFFICIENTS37[index],1<<37)
            assert old==expected,(SITES[index],str(old),str(expected))
            new=Fraction(2*NEW_TURN_UNITS50[index],1<<50)
            assert angle_class(new)=='generic'
            self.records.append(dict(index=index,site=SITES[index],target=str(target),old_half_turns=str(old),new_half_turns=str(new)))
            self.generic+=1
            return self.builder.z_pow(target,new)
        if kind=='T':self.T+=1
        else:self.Clifford+=1
        return self.builder.z_pow(target,old)

    def finish(self):
        assert(self.generic,self.T,self.Clifford)==(34,4,1),(self.generic,self.T,self.Clifford)
        return self.records


def phase_endpoint(builder,token):
    proxy=AngleProxy(builder);result=ORIGINAL_ENDPOINT(proxy,token)
    LAST_PROXY_RECORDS.clear();LAST_PROXY_RECORDS.extend(proxy.finish())
    return result


def install():
    global _INSTALLED
    variant_gate()
    if not _INSTALLED:
        previous.install()
        assert divider.phase_endpoint is ORIGINAL_ENDPOINT,'Unexpected pre-existing endpoint replacement.'
        divider.phase_endpoint=phase_endpoint;_INSTALLED=True
    return divider


def load_baseline(name):return previous.load_baseline(name)
