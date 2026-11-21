# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0
# Credits: Opus and Astra.
"""Isolated candidate03 root-tail specialization; no baseline file edits."""
from pathlib import Path
import hashlib,importlib.util,json,os,sys
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
HERE=Path(__file__).resolve().parent;NARROW=HERE.parents[1];BASE=HERE.parent/'candidate01'
for pin in json.loads((HERE/'INPUTS.json').read_text())['files']:
    raw=(NARROW/pin['path']).read_bytes()
    assert len(raw)==pin['bytes']and hashlib.sha256(raw).hexdigest()==pin['sha256'],pin['path']
path=HERE.parent/'candidate02/variant.py'
spec=importlib.util.spec_from_file_location('candidate03_pinned_candidate02_variant',path)
previous=importlib.util.module_from_spec(spec);sys.modules[spec.name]=previous;spec.loader.exec_module(previous)
import consuming_odd_sqrt as root
ORIGINAL_ROOT_STEP=root._root_step
common=previous.common


def root_step(builder,remainder,older,b,*,initial=False,inverse=False):
    # At every real loop cut len(remainder)=j+3. Only j11 and j12 append
    # known-zero input pairs; all earlier iterations keep the original code.
    if len(remainder)<14:
        return ORIGINAL_ROOT_STEP(builder,remainder,older,b,initial=initial,inverse=inverse)
    assert len(remainder)in(14,15)and not initial and isinstance(b,common.km.q)
    low=list(remainder[:3]);high=list(remainder[3:]);older=list(older)
    assert b not in list(remainder)+older
    if not inverse:builder.x(low[0]);builder.x(low[1])
    builder.cx(b,root._arr(high))
    if inverse:
        root._add_leading_one(builder,high,inverse=True)
        root.add(builder,older,high,carry_in=b,subtract=True)
    else:
        root.add(builder,older,high,carry_in=b)
        root._add_leading_one(builder,high)
    builder.cx(b,root._arr(high))
    if inverse:builder.x(low[0]);builder.x(low[1])


def variant_gate():
    gate=previous.variant_gate()
    accepted=common.checked_json(NARROW/'PAPER_GATE_RECEIPT_012_VARIANT.json',
        'f11816ec390d58f379a7dc63704fab80a385bb581c73ec729c8e199697ad5131')
    assert accepted['native_build_authorized_after_this_receipt']and accepted['preserve_candidate01']and accepted['preserve_candidate02']
    primary=gate['primary'];primary['complete_components']['consuming_root']=198
    primary['Toffolis_expected']=accepted['expected_Toffolis']
    primary['total_E']=accepted['total_equivalents'];primary['paper_cost']=accepted['predicted_cost']
    primary['root_peak_with_flags']=41
    primary['margins']={name:threshold-primary['paper_cost']for name,threshold in [('stage97',92278.95),('target',89987),('stretch',82740)]}
    assert primary['Toffolis_expected']==1562.5 and primary['T']==4 and primary['R']==34
    assert primary['paper_cost']==88733.03208522254
    gate['status']='ACCEPTED_CANDIDATE03_ROOT_TAIL_GATE_NATIVE_PENDING'
    return gate


def install():
    previous.install();variant_gate();root._root_step=root_step
    return root


def load_baseline(name):return previous.load_baseline(name)
