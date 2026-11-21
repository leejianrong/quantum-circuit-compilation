# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0
# Credits: Opus and Astra.
"""Isolated Q48 inverse divider with exact disposable feed-carry callbacks."""
from pathlib import Path
import hashlib

HERE=Path(__file__).resolve().parent;NARROW=HERE.parents[1]
BASE=HERE.parent/'candidate01'
BASE_DIVIDER_SHA='d0dbaf6fe4227da988c9cb9e9dee847624992c7c5cce7ab347990d5b0a116c05'
assert hashlib.sha256((BASE/'divider.py').read_bytes()).hexdigest()==BASE_DIVIDER_SHA
_divider=None


def bind(divider_module):
    """Bind the parent's pinned divider, without installing any hook itself."""
    global _divider
    assert Path(divider_module.__file__).resolve()==(BASE/'divider.py').resolve()
    assert hashlib.sha256(Path(divider_module.__file__).read_bytes()).hexdigest()==BASE_DIVIDER_SHA
    required=('_feed_carry','_feed_erase','_frame','_leading_offset','_dirty','inverse_add','cleanup_u12')
    assert all(callable(getattr(divider_module,name,None)) for name in required)
    if _divider is not None:assert _divider is divider_module
    _divider=divider_module
    return cleanup_divider


def install(divider_module):
    """Replace only this process's inverse hook on the supplied divider."""
    divider_module.cleanup_divider=bind(divider_module)
    return divider_module


def cleanup_divider(builder,token):
    """Reverse all24 rows, repay every phase, then return current P15 owners."""
    assert _divider is not None,'Parent must bind the pinned divider before use.'
    d=_divider
    assert builder.max_qubits==48 and builder.num_allocated_qubits==43
    assert not token.consumed and len(token.rows)==24
    assert [j for j,k,debt in token.rows]==list(range(12,36))
    assert all(not debt.consumed for j,k,debt in token.rows)
    token.consumed=True;v=token.v;released_rows=[]
    for j,k,debt in reversed(token.rows):
        u=token.u
        if j<=24:
            low=u[0];target=u[1:];sign=token.history[j]
            cur=token.P[23-j] if j<24 else None
            if j<24:assert cur is not None
            carry=d._feed_carry(builder,v,low,cur,sign)
            d._frame(builder,sign,target);d._leading_offset(builder,target,inverse=True)
            released_input=d.inverse_add(builder,v[1:],target,debt,carry_in=carry,dirty_wires=d._dirty(token),
                carry_lifecycle=(
                    lambda value: d._feed_erase(builder,value,v,low,cur,sign),
                    lambda: d._feed_carry(builder,v,low,cur,sign)))
            d._frame(builder,sign,target)
            if not released_input:d._feed_erase(builder,carry,v,low,cur,sign)
            assert released_input,'Every pinned Q48 feed partition must release its owned input carry.'
            released_rows.append(j)
            if cur is not None:builder.cx(cur,low)
            builder.cx(sign,low);builder.cx(v[0],low)
            token.P[24-j]=low;token.u=target+[sign];del token.history[j]
        else:
            builder.cx(v[0],u[0]);sign=u[0];target=u[k+1:]
            d._frame(builder,sign,target);d._leading_offset(builder,target,inverse=True)
            d.inverse_add(builder,v[k+1:],target,debt,carry_in=v[k],dirty_wires=d._dirty(token))
            d._frame(builder,sign,target);token.u=u[1:]+u[:1]
        assert debt.consumed and not debt.measurements
        assert builder.num_allocated_qubits==43
        live=token.v+token.flags+token.u+[q for q in token.P if q is not None]+list(token.history.values())
        assert len(live)==len(set(live))==43
    assert sorted(released_rows)==list(range(12,25))
    assert tuple(token.u)==token.initial_u and not token.history
    token.P=d.cleanup_u12(builder,v,token.P,token.u)
    assert builder.num_allocated_qubits==31 and all(q is not None for q in token.P)
    assert len(set(v+token.flags+list(token.P)))==31
    assert all(debt.consumed and not debt.measurements for j,k,debt in token.rows)
    return list(token.P)


COMPONENT_CONTRACT=dict(Q=48,divider_core_E=587.5,feed_conditional_regeneration_E=6.5,
    disposable_feed_rows=tuple(range(12,25)),paired_debts=24,entry_live_owners=43,
    returned_current_product_owners=15,final_live_owners=31,
    initialization='Parent retains candidate02 triangular u12 initializer and original exact cleanup.')
