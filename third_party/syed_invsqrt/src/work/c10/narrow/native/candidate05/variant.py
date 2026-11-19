# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0
# Credits: Opus and Astra.
"""Isolated candidate05; pinned04 angles and exactly one route omission."""
from pathlib import Path
import copy,hashlib,importlib.util,json,sys

HERE=Path(__file__).resolve().parent;NARROW=HERE.parents[1];PREVIOUS=HERE.parent/'candidate04'
BASE=HERE.parent/'candidate01'
INPUTS=json.loads((HERE/'INPUTS.json').read_text())


def verify_inputs():
    for pin in INPUTS['files']:
        raw=(NARROW/pin['path']).read_bytes()
        assert len(raw)==pin['bytes'] and hashlib.sha256(raw).hexdigest()==pin['sha256'],pin['path']


verify_inputs()
spec=importlib.util.spec_from_file_location('candidate05_pinned_candidate04_variant',PREVIOUS/'variant.py')
previous=importlib.util.module_from_spec(spec);sys.modules[spec.name]=previous;spec.loader.exec_module(previous)
common=previous.common;divider=previous.divider
BOUND=previous.BOUND;COEFFICIENTS37=previous.COEFFICIENTS37;NEW_TURN_UNITS50=previous.NEW_TURN_UNITS50;SITES=previous.SITES
ACCEPTED=common.checked_json(NARROW/'PAPER_GATE_RECEIPT_016_VARIANT.json',
    '141d51af466cea914cc9c318e09c34558b7c23c6247fbf5e87c9ea9f1efa7cbe')
assert ACCEPTED['native_build_authorized'] and ACCEPTED['all_native_candidates_preserved']==[1,2,3,4]
NEW_CENTRES=tuple(ACCEPTED['centres']);OLD_CENTRES=tuple(divider.CENTRES)
assert NEW_CENTRES==(-1,-3,-7,-1,-2) and OLD_CENTRES==(0,-2,-6,0,-1)
ORIGINAL_ROUTE=divider._route;ORIGINAL_SLOTS=divider._slots()
ROUTE_TRACE=[];_INSTALLED=False


def checked_quantized():
    result,digest=previous.checked_quantized()
    assert digest==ACCEPTED['source_pins']['research/postgate_angle_refit/quantize50.json']
    assert result['exact_statistics']['quantized50']['minimum_margin_units']==124372027
    assert result['rotation_charge']==ACCEPTED['rotation_charge']
    return result,digest


def variant_gate():
    verify_inputs();result=copy.deepcopy(previous.variant_gate());quantized,digest=checked_quantized()
    proof=json.loads((PREVIOUS/'whole_native_text_all.json').read_text())
    assert proof['whole_official_domain'] and proof['proved_inputs']==3133452 and proof['every_HMR_transcript_proved']
    assert proof['phase_modulus']==1<<50 and proof['phase_units50_sha256']==quantized['quantized_phase50_sha256']
    assert proof['circuit_sha256']==ACCEPTED['source_pins']['native/candidate04/candidate04.kmb']
    assert sum(ACCEPTED['Toffoli_components'].values())==1560.5
    p=result['primary'];p['Toffolis_expected']=1560.5;p['phase']['Toffolis']=144
    # The inherited component phase_direct includes the4T/4 equivalent.
    assert p['complete_components']['phase_direct']==147
    p['complete_components']['phase_direct']=145
    p['total_E']=ACCEPTED['complete_predicted_E'];p['paper_cost']=ACCEPTED['complete_predicted_cost']
    p['rotation_charge']=ACCEPTED['rotation_charge'];p['complete_components']['rotation_charge']=ACCEPTED['rotation_charge']
    p['quantized_exact_minimum_margin_units64']=124372027
    p['margins']={name:limit-p['paper_cost'] for name,limit in [('stage97',92278.95),('target',89987),('stretch',82740)]}
    assert p['Q']==49 and p['T']==4 and p['R']==34
    assert p['first_loader_peak']==p['second_loader_peak']==49
    result['status']='ACCEPTED_CANDIDATE05_ROUTE_ONLY_GATE_NATIVE_PENDING'
    result['candidate05_exact_Toffoli_components']=ACCEPTED['Toffoli_components']
    return result


def operation_count(builder):
    from branch_prover import Program,generated_text
    return len(Program(generated_text(builder.finish_circuit())).operations)


def route(builder,word,variables,inverse=False):
    """Existing five affine controls; translated matchings; one identity skip."""
    assert len(word)==27 and tuple(divider.CENTRES)==NEW_CENTRES
    start=operation_count(builder);stages=list(range(5))
    if inverse:stages.reverse()
    old_gates=[];new_gates=[];omissions=[]
    for stage in stages:
        with divider._affine_control(builder,variables,divider.CONTROLS[stage]) as control:
            for i in range(27):
                k=(OLD_CENTRES[stage]-i)%27
                if i<k:old_gates.append([str(control),str(word[i]),str(word[k])])
            for i in range(27):
                k=(NEW_CENTRES[stage]-i)%27
                if i>=k:continue
                if(stage,i,k)==(0,0,26):
                    omissions.append(dict(stage=stage,positions=[i,k],control=str(control),owners=[str(word[i]),str(word[k])]))
                    continue
                builder.cswap(control,word[i],word[k]);new_gates.append([str(control),str(word[i]),str(word[k])])
    stop=operation_count(builder)
    assert len(old_gates)==65 and len(new_gates)==64 and len(omissions)==1
    ROUTE_TRACE.append(dict(inverse=inverse,start=start,stop=stop,old_cswap_arguments=old_gates,
                            new_cswap_arguments=new_gates,omissions=omissions))


def install():
    global _INSTALLED
    variant_gate()
    if not _INSTALLED:
        previous.install();assert divider._route is ORIGINAL_ROUTE
        divider.CENTRES=NEW_CENTRES;divider._route=route
        assert divider._slots()==ORIGINAL_SLOTS,'Common centre offset unexpectedly changed phase sites.'
        _INSTALLED=True
    return divider


def load_baseline(name):return previous.load_baseline(name)


def proof50_module():
    """Load frozen04 proof helpers/oracle; this variant supplies its own main."""
    name='candidate05_pinned_candidate04_proof50'
    if name not in sys.modules:
        sys.path.insert(0,str(PREVIOUS))
        spec=importlib.util.spec_from_file_location(name,PREVIOUS/'prove50.py')
        module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    module=sys.modules[name]
    assert module.variant is sys.modules['variant'] and module.MODULUS==1<<50
    return module
