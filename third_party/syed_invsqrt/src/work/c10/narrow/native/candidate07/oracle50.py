# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0
# Credits: Opus and Astra.
"""New ring26 oracle; explicit pinned arithmetic and exact direct/delta phases."""
from pathlib import Path
import hashlib,importlib.util,sys
import numpy as np
import variant

MAX_X=3133452;MODULUS=1<<50;MASK=np.uint64(MODULUS-1)
MODEL_PATH=variant.BASE/'whole_model.py'
MODEL_SHA='740b3530990003de29fc3a29726c1ac7f97aa29467fc14fd7608f5c5f58bfca4'
assert hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest()==MODEL_SHA
assert Path(sys.modules['common'].__file__).resolve()==(variant.BASE/'common.py').resolve()
_name='candidate07_pinned_original_integer_arithmetic_model'
if _name not in sys.modules:
    _spec=importlib.util.spec_from_file_location(_name,MODEL_PATH)
    _module=importlib.util.module_from_spec(_spec);sys.modules[_name]=_module;_spec.loader.exec_module(_module)
_model=sys.modules[_name]
assert Path(_model.__file__).resolve()==MODEL_PATH.resolve() and _model.MAX_X==MAX_X
COEFFICIENTS37=tuple(1<<(i+1)for i in range(26))+tuple(1<<(27+j)for j in range(7))+(1,)
SITES=tuple(f'base_i{i}'for i in range(26))+tuple(f'overflow_j{j}'for j in range(7))+('global_one',)
ANGLES=tuple(variant.NEW_TURN_UNITS50)
assert tuple(variant.SITES)==SITES and len(ANGLES)==34 and ANGLES[-1]==0
DELTA50=tuple(a-(c<<13)for a,c in zip(ANGLES,COEFFICIENTS37))
_fit,_fit_sha=variant.accuracy_receipt()
assert _fit_sha=='c0eab1edd234e32d5baa1a51a0fec46abf82165d3973ffda825d2149f67f11e5'
assert list(ANGLES)==_fit['new_angles_units50']
assert [v*(1<<14)for v in DELTA50]==_fit['quantized_delta_turn_units64']
EXPECTED_PHASE_SHA256=_fit['exact_screen']['phase50_sha256']


def phase_units50(xs):
    old,chart=_model.phase_units(xs,return_chart=True)
    old=np.asarray(old,dtype=np.int64);k=np.asarray(chart['flags'],dtype=np.int64)
    assert np.all((k>=0)&(k<=10)) and np.all((old>=0)&(old<(1<<37)))
    z=old&((1<<27)-1);P=((z>>k)|(z<<(27-k)))&((1<<27)-1)
    assert np.all((P&1)==1) and np.all((P>>26)==1)
    assert np.array_equal(((P<<k)+(P>>(27-k)))&((1<<37)-1),old)
    W=P>>1;r=((W<<k)|(W>>(26-k)))&((1<<26)-1);w=W>>(26-k)
    baseline=2*r+(1<<27)*(r&((1<<k)-1))+1
    assert np.array_equal(baseline,2*W*(1<<k)+2*w+1)
    assert np.array_equal(baseline-(P*(1<<k)+w),w+1-(1<<k))
    direct=np.zeros(len(old),dtype=np.int64);delta=np.zeros(len(old),dtype=np.int64)
    for i in range(34):
        if i<26:feature=(r>>i)&1
        elif i<33:
            j=i-26;feature=((r>>j)&1)*(k>j)
        else:feature=np.ones(len(old),dtype=np.int64)
        direct+=feature*ANGLES[i];delta+=feature*DELTA50[i]
    for j in(7,8,9):direct+=((r>>j)&1)*(k>j)*(1<<(40+j))
    a=direct.astype(np.uint64)&MASK
    b=((baseline.astype(np.uint64)<<np.uint64(13))+delta.astype(np.uint64))&MASK
    assert np.array_equal(a,b),'New ring26 direct phase and independently scaled baseline disagree.'
    return a
