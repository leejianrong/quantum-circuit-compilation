# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0
# Credits: Opus and Astra.
"""tk_q46 CAP-AWARE copy (work cap and complete peak read from the certificate: cap 19 -> peak 46) of the lead copy of agents/width/src/q47_loaders_own.py (itself a COPY by agent width of Pro 2 q47_loaders.py: the SECOND loader only, reading an own cap-20 search result
(agents/width/loader_search, constructor v5_q47 run on this Mac) instead of second90_paper.json. load() unchanged.

Original-interface first70/second90 coefficient loaders at strict Q47.

All consumed coordinates retain their exact original-raw128 phase truth in
the original TableDebts class. This module emits no output-test phase tags.
"""
from pathlib import Path
from functools import lru_cache
from types import SimpleNamespace
import hashlib,json
HERE=Path(__file__).resolve().parent
import os
OWN_SECOND=Path(os.environ.get('TK46_SECOND_JSON') or os.environ.get('LEAD_SECOND_JSON'))  # lead: certificate chosen from runs/loader_sweep
def _own_spec():
    data=json.loads(OWN_SECOND.read_text())
    hmr=sum(len(st['discarded_truths']) for st in data['steps'] if st['kind']=='Clifford_frame_then_HMR')
    return dict(path=OWN_SECOND,sha=hashlib.sha256(OWN_SECOND.read_bytes()).hexdigest(),
     mode='second_framed',Toffolis=data['Toffolis'],HMR_debts=hmr,work_cap=data['work_cap'],entry=31,returned=43,peak=27+data['work_cap'],
     fixed=(3,5,6),reused=(0,1,2,4),outside=27)
SPECS={'second':_own_spec()}
LAST_REPORT=None


@lru_cache(maxsize=2)
def certificate(which):
    spec=SPECS[which];path=spec['path']
    assert hashlib.sha256(path.read_bytes()).hexdigest()==spec['sha']
    data=json.loads(path.read_text())
    assert data['status']=='COMPLETE_MATHEMATICAL_LOADER_NOT_NATIVE'
    assert data['mode']==spec['mode']and data['Toffolis']==spec['Toffolis']
    assert data['work_cap']==data['work_peak']==spec['work_cap']
    assert data['complete_other_owner_count']==spec['outside']and data['complete_peak']==spec['peak']
    assert data['fixed_address_slots']==list(spec['fixed'])and data['reusable_input_slots']==list(spec['reused'])
    assert data['model_sha256']=='24fff823faa911afe93d02afc3ded0bbd156a210a85f1265c989a087f8fd1219'
    assert data['codebook_source_sha256']=='9c6073d78becea467d37805131fdcc572e530c72acef5664b08057ef883f17be'
    return data


def load(builder,address7,which,debts,*,table_api):
    global LAST_REPORT
    api=table_api;common=api.common;km=common.km;cb=common.cb
    spec=SPECS[which];data=certificate(which);address=list(address7)
    assert builder.max_qubits>=spec['peak'] and builder.num_allocated_qubits==spec['entry']
    assert len(address)==len(set(address))==7 and all(isinstance(q,km.q)for q in address)
    assert isinstance(debts,api.TableDebts)
    before=debts.total_recorded;fixed=[address[i]for i in spec['fixed']]
    work=[address[i]for i in spec['reused']];cap=spec['work_cap'];offset=1+len(fixed)
    available=list(builder.alloc_qubits(cap-len(work)));all_mutable=list(work+available)
    assert builder.num_allocated_qubits==spec['peak'] and spec['entry']-len(work)==spec['outside']
    count=0;trace=[spec['peak']]
    for item in data['steps']:
        kind=item['kind']
        if kind in('bank','CCX_new_coordinate'):
            target=available.pop(0);plan=common.plan_from_json(item['plan'])
            cb.emit_xor(builder,fixed+work,target,plan);work.append(target);count+=plan.and_count
        elif kind=='Clifford_zero_dependent_coordinate':
            index=item['index'];target=work[index]
            api._BASE._affine_xor(builder,fixed,work[:index],target,item['expression'])
            work.pop(index);available.append(target)
        elif kind=='Clifford_frame_then_HMR':
            assert item['affine_fixed_offset']==offset
            api.emit_affine_frame(builder,fixed,work,item['full_affine_rows'])
            kept=item['retained_count'];discard=work[kept:]
            assert len(discard)==len(item['discarded_truths'])
            for wire,truth in zip(discard,item['discarded_truths']):
                debts.erase(builder,wire,int(truth,16));available.append(wire)
            work=work[:kept]
        elif kind=='virtual_affine_product':pass
        elif kind=='XOR_product_existing_coordinate':
            assert item['target_index']==0
            plan=common.plan_from_json(item['plan'])
            cb.emit_xor(builder,fixed+work[1:],work[0],plan);count+=plan.and_count
        elif kind=='final_output_Clifford_frame':
            api.emit_affine_frame(builder,fixed,work,[int(row)<<offset for row in item['matrix_rows']])
        else:raise AssertionError(('Unknown exact loader step',kind))
        assert len(work)+len(available)==cap and len(set(work+available))==cap
        assert not set(fixed)&set(work+available)
        trace.append(builder.num_allocated_qubits)
    assert len(work)==16 and count==spec['Toffolis']
    assert debts.total_recorded-before==spec['HMR_debts']
    if available:builder.free(common.array(available))
    trace.append(builder.num_allocated_qubits)
    assert builder.num_allocated_qubits==spec['returned']and max(trace)==spec['peak']
    LAST_REPORT=dict(loader=which,Toffolis=count,HMR_debts=debts.total_recorded-before,
        entry=spec['entry'],outside_mutable_owners=spec['outside'],work_cap=cap,
        existing_input_work=len(spec['reused']),fresh_zero_owners=cap-len(spec['reused']),
        fixed_address_slots=list(spec['fixed']),retired_address_slots=list(spec['reused']),
        returned=spec['returned'],peak=max(trace),owner_trace=trace,
        fixed_owners=list(map(str,fixed)),mutable_owners=list(map(str,all_mutable)),
        output_owners=list(map(str,work)),paper_sha256=spec['sha'],all_debts_in_original_raw128_order=True)
    return list(work[:13]),list(work[13:])


def adapter(original_tables07):
    def load_joint16(builder,address7,*,variant,debts):
        assert variant in SPECS
        return load(builder,address7,variant,debts,table_api=original_tables07)
    result=SimpleNamespace(**{k:v for k,v in vars(original_tables07).items()if not k.startswith('__')})
    result.load_joint16=load_joint16;result._source_api=original_tables07
    result.RESOURCES={k:dict(v)for k,v in original_tables07.RESOURCES.items()}
    for which,s in SPECS.items():
        result.RESOURCES[which].update(Toffolis=s['Toffolis'],HMR_debts=s['HMR_debts'],
            other_fixed_owners=s['outside'],work_cap=s['work_cap'],existing_input_work=len(s['reused']),
            new_zero_owners=s['work_cap']-len(s['reused']),complete_peak=s['peak'],return_owners=s['returned'])
    assert result.TableDebts is original_tables07.TableDebts
    return result
