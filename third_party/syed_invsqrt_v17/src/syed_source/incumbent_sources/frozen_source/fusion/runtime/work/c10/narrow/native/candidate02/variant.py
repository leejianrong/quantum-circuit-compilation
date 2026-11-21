# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0
# Credits: Opus and Astra.
"""Isolated native variant; imports only pinned owned baseline sources."""
from pathlib import Path
import copy,hashlib,importlib.util,json,os,sys
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
HERE=Path(__file__).resolve().parent;BASE=HERE.parent/'candidate01';NARROW=HERE.parents[1]
INPUTS=json.loads((HERE/'INPUTS.json').read_text())
for pin in INPUTS['files']:
    raw=(NARROW/pin['path']).read_bytes()
    assert len(raw)==pin['bytes']and hashlib.sha256(raw).hexdigest()==pin['sha256'],pin['path']
sys.path.insert(0,str(BASE))
import common
import divider as baseline_divider


def load_baseline(name):
    path=BASE/(name+'.py');module_name='candidate02_pinned_'+name
    if module_name in sys.modules:return sys.modules[module_name]
    spec=importlib.util.spec_from_file_location(module_name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[module_name]=module;spec.loader.exec_module(module)
    return module


def initialize_u12(builder,v,P,u):
    """13-CCX direct triangular construction, followed by two exact HMRs."""
    d=baseline_divider;P=list(P)
    for i in range(4):
        item=d.LOCAL['low_cleanup'][i]
        env={f'v{j}':v[j]for j in range(i+1)}
        env.update(p12=P[12],p13=P[13],p14=P[14])
        env.update({f'u{j}':u[j]for j in range(i)})
        d.cb.emit_xor(builder,[env[name]for name in item['inputs']],u[i],d.plan_from_json(item['plan']))
    def aa(i):return(1,1<<i)if 0<=i<12 else(0,0)
    def bb(i):return(1,0)if i in (0,13)else(1,1<<(i-1))
    for i in range(4,14):
        plan=d._compose(d.HIGH,[aa(i),bb(i),aa(i-2),aa(i-3),aa(i-1),(0,1<<12)],13)
        d.cb.emit_xor(builder,list(v)+[u[i-1]],u[i],plan)
    variables=[v[0],v[1],P[12],u[0],u[1]]
    d._erase(builder,P[13],variables,d.P13);d._erase(builder,P[14],variables,d.P14)
    P[13]=None;P[14]=None
    return P


def variant_gate():
    base=common.verify_gate_sources()
    accepted=common.checked_json(NARROW/'PAPER_GATE_RECEIPT_011_VARIANT.json',
        '27a5fae99ae9ce4fed8602b52160618a25b56c56b30ea34b8101b64b161e53be')
    mathematical=common.checked_json(NARROW/'research/recompute_root/initializer_u12_triangular/complete_gate.json',
        'fc9626c050ad286dadcbb02ce5e901f7c651748dd804bd41c1ba564450ca7e7f')
    assert accepted['native_build_authorized_after_this_receipt']and accepted['preserve_candidate01']
    result=copy.deepcopy(base);primary=result['primary']
    primary['complete_components']=mathematical['complete_components']
    primary['Toffolis_expected']=accepted['expected_Toffolis']
    primary['total_E']=accepted['total_equivalents'];primary['paper_cost']=accepted['predicted_cost']
    primary['rotation_charge']=accepted['rotation_charge']
    primary['margins']=mathematical['margins'];primary['core_change']['new_core']=577.5
    primary['core_change']['direct_u12']=14;primary['core_change']['saving_E']=28.0
    primary['u12_initializer_peak']=45
    assert primary['Toffolis_expected']==1570.5 and primary['T']==4 and primary['R']==34
    assert primary['paper_cost']==89125.03208522254
    result['status']='ACCEPTED_CANDIDATE02_TRIANGULAR_U12_VARIANT_GATE_NATIVE_PENDING'
    return result


def install():
    """Change only this process's imported initializer, never an on-disk file."""
    variant_gate();baseline_divider.initialize_u12=initialize_u12
    return baseline_divider
