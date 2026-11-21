# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# Credits: Syed Asad Ali, working with a team of AI agents (GPT-6 Astra Pro, Gemini 4 Argon, Fable 5.2, Mythos 5.2 and Opus 5.5), with Claude Science supporting the research.
"""Candidate12 endpoint with a measured/rebuilt unused residue owner.

Root12 phase38 endpoint with an in-place extra quotient sign.

The unused u12 remainder owner is transformed reversibly into sigma37.
The old row35 state is restored after the phase endpoint, so the existing
divider inverse and every deferred carry transcript remain unchanged.
"""
import json
import sys
import endpoint45_core as helpers
import endpoint38_core as core

ANGLE_FILE=None
LAST_CUT=10
ROUTING_CAP=45
REPORT={}


def extra_sign(b,v,u):
    """XOR sigma37's five-input correction into u12; this is an involution."""
    t0,t1,t2,s,a,z=u[10],u[11],u[12],u[13],v[10],v[11]
    if LAST_CUT==11:
        b.cx(z,t2);b.x(z);b.cx(t1,s);b.x(s);b.ccx(s,z,t2)
        b.x(s);b.cx(t1,s);b.x(z);return
    assert LAST_CUT==10
    g=b.alloc_qubits(1)[0]
    for q in (a,z):b.cx(t0,q);b.cx(t1,q)
    b.ccx(a,z,g)
    for q in (z,a):b.cx(t1,q);b.cx(t0,q)
    b.x(t2);b.cx(t1,t2);b.cx(s,t2)
    b.cx(t1,s);b.cx(t0,g);b.cx(t1,g);b.ccx(s,g,t2)
    b.cx(t1,g);b.cx(t0,g);b.cx(t1,s)
    for q in (a,z):b.cx(t0,q);b.cx(t1,q)
    b.del_and(a,z,g)
    for q in (z,a):b.cx(t1,q);b.cx(t0,q)
    b.free(g)


def apply(ctx):
    data=json.loads(ANGLE_FILE.read_text());angles=list(map(int,data['new_angles_units50']))
    assert len(angles)==35 and angles[-1]==0
    assert data.get('phase_word_units')==38 and data.get('last_zero') is True
    d=ctx.old.divider
    module=sys.modules['variant_patch_patch_endpoint_v9e2']
    form=module._core.RETIRE_V9;assert module._core.V10_FROM_G1
    def endpoint(real,token):
        v,u,flags=token.v,token.u,token.flags
        assert len(u)==14 and len(v)==12 and real.num_allocated_qubits==43
        cap=real.max_qubits;assert cap in (44,45,46);helpers.QMAX=cap
        extra_sign(real,v,u)
        d._sigma25_frame(real,v,u)
        for q in u[:9]:real.cx(v[0],q)
        real.cx(v[1],u[9])
        h12,h13,h14=token.history[12],token.history[13],token.history[14]
        v9,v10,v11=v[9],v[10],v[11]
        unused=u[11]
        unused_outcome=real.alloc_bits(1)[0];real.hmr(unused,unused_outcome)
        builder=helpers.SpareProxy(real,43);builder.limit=7
        builder.spare.append(unused);builder.lent.add(unused)
        m11=real.alloc_bits(1)[0];real.hmr(v11,m11)
        real.push_condition(m11);real.z(h12);real.z(v10);real.cz(v10,h13);real.pop_condition();real.free(m11)
        builder.spare.append(v11);builder.lent.add(v11)
        m10=real.alloc_bits(1)[0];real.hmr(v10,m10);builder.spare.append(v10);builder.lent.add(v10)
        m9=real.alloc_bits(1)[0];real.hmr(v9,m9);builder.spare.append(v9);builder.lent.add(v9)
        signs={**token.history,25:u[10],26:u[9],36:u[13],37:u[12]}
        signs.update({j:u[35-j] for j in range(27,36)})
        assert sorted(signs)==list(range(12,38)) and len(set(signs.values()))==26
        for q in signs.values():real.x(q)
        core.emit(d,builder,[signs[37-i] for i in range(26)],flags,angles,ROUTING_CAP)
        for q in signs.values():real.x(q)
        real.cx(v[1],u[9])
        for q in u[:9]:real.cx(v[0],q)
        assert set(builder.spare)=={v9,v10,v11,unused}
        builder.spare.remove(unused);builder.lent.remove(unused)
        named={f'v{i}':v[i] for i in range(12)}
        named.update({f's{k}':q for k,q in token.history.items()})
        builder.spare.remove(v11)
        if cap==44:
            class LastHelperBorrow(helpers.SpareProxy):
                allocations=0
                def alloc_qubits(self,count):
                    assert count==1
                    self.allocations+=1
                    if self.allocations==3:
                        self.spare.append(v10);self.lent.add(v10)
                    return super().alloc_qubits(count)
            helper_proxy=LastHelperBorrow(real,real.num_allocated_qubits)
        else:helper_proxy=helpers.SpareProxy(real,real.num_allocated_qubits)
        helper_proxy.spare=[v11];helper_proxy.lent={v11};helper_proxy.limit=7
        gvals,kept=helpers._emit_form(helper_proxy,form,named,v9,keep=True)
        if cap==44:
            assert kept[-1][0]==v10
            helpers._erase_helpers(helper_proxy,[kept.pop()])
            helper_proxy.spare.remove(v10);helper_proxy.lent.remove(v10)
        real.push_condition(m9);real.z(v9);real.pop_condition();real.free(m9);builder.spare.remove(v9)
        g1=gvals[len(form['inputs'])+1]
        real.cx(v9,v10);real.cx(g1,v10)
        wa,wb,ops=helpers._pair_forms(real,[h13,g1],[v9,h14]);real.ccx(wa,wb,v10);helpers._undo(real,ops)
        helpers._erase_helpers(helper_proxy,kept);assert helper_proxy.spare==[v11]
        builder.spare.append(v11)
        real.push_condition(m10);real.z(v10);real.pop_condition();real.free(m10);builder.spare.remove(v10)
        d._sigma25_frame(real,v,u,inverse=True)
        assert builder.spare==[v11]
        real.cx(h12,v11);real.cx(v10,v11);real.ccx(v10,h13,v11)
        # Raw post-row35 chart: sigma25=u10^v1, sigma26=u9^v0.
        for q in (token.history[24],v11,v[0],v[1]):real.cx(q,unused)
        wa,wb,ops=helpers._pair_forms(real,[v[0],v[1]],[u[10],u[9]])
        real.ccx(wa,wb,unused);helpers._undo(real,ops)
        real.push_condition(unused_outcome);real.z(unused);real.pop_condition();real.free(unused_outcome)
        extra_sign(real,v,u)
        assert real.num_allocated_qubits==43
        REPORT.update(cap=cap,maximum_extra_owners=builder.max_extra,last_cut=LAST_CUT,routing_cap=ROUTING_CAP,unused_residue_rebuild_toffolis=1,
                      phase_ring_bits=27,extra_sign_roundtrip_toffolis=4 if LAST_CUT==10 else 2)
    d.phase_endpoint=endpoint
