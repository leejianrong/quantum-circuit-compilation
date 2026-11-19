# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""prodcoef patch SEEDINV: retire raw v0, v1, v3 over the whole inverse product,
then recover them by running the three seed rows backwards.

Facts used (exact, from the seed forward in the seed root frame):
  seed row j (j=0,1,2) has sign s_j = NOT c_j with c = (v0', v1', v3') and its
  sign copy is appended as seed[3+j] = s_j; rows j+1.. then add into seed[3+j].
After the inverse product restores the seed, inverting seed row 2 (sign wire
seed[5]) returns seed[4] = s1; inverting row 1 (sign seed[4]) returns
seed[3] = s0; inverting row 0 (sign seed[3]) returns seed[0:3] = 111.  So the
three sign wires ARE NOT v0', NOT v1', NOT v3': one X each, then the unchanged
seed-root inverse frame gives raw v0, v1, v3 on those wires, where their HMR
outcomes are paid by Z.  The six seed carry debts are paid natively by the
three inverse rows.  No helper, no phase plan, no fresh wire.

Cost: inverse product runs with 41 data owners (vs 43), seed rows inverse 9,
frame inverse 1.  Replaces lifecycle.product_inverse and baseline.seed_cleanup.
"""

STATE = {}


def product_inverse(builder, v, D, word, token, dirty, *, baseline):
    km = baseline.km
    D, word, dirty = list(D), list(word), list(dirty)
    assert len(D) == 13 and len(word) == 16 and len(token.rows) == 10
    entry = builder.num_allocated_qubits
    outcomes = {}
    for i in (0, 1, 3):
        old = v[i]
        assert isinstance(old, km.q) and dirty.count(old) == 1
        m = builder.alloc_bits(1)[0]
        builder.hmr(old, m)
        builder.free(old)
        outcomes[i] = m
        v[i] = None
        dirty.remove(old)
    C = [False] + D
    builder.x(word[15])
    for i in reversed(range(10)):
        debt = token.rows[i]
        q = word[6 + i]
        target = word[:6 + i]
        source = C[9 - i:] if i < 9 else C
        for t in target:
            builder.cx(q, t)
        carry = baseline._product_carry(builder, C, q, i)

        def erase(value, i=i, q=q):
            baseline._clear_product_carry(builder, C, q, i, value)

        def regenerate(i=i, q=q):
            return baseline._product_carry(builder, C, q, i)

        released = baseline.product_ar.inverse_add(
            builder, source, target, debt, carry_in=carry,
            dirty_wires=dirty + word[6:],
            carry_lifecycle=(erase, regenerate) if i < 8 else None)
        if not released:
            baseline._clear_product_carry(builder, C, q, i, carry)
        for t in target:
            builder.cx(q, t)
        assert debt.consumed and not debt.measurements
    builder.x(word[15])
    assert builder.num_allocated_qubits == entry - 3
    STATE['outcomes'] = outcomes
    return word[:6], word[6:]


def make_seed_cleanup(b):
    ar, km = b.ar, b.km

    def seed_cleanup(builder, v, D, seed, token):
        seed = list(seed)
        assert len(seed) == 6 and len(token.rows) == 3
        assert all(v[i] is None for i in (0, 1, 3))
        outcomes = STATE.pop('outcomes')
        for j in reversed(range(3)):
            ar.inverse_signed_row(builder, D, seed[:3 + j], token.rows[j],
                                  shift=-(11 - j), sign=seed[3 + j])
        builder.x(km.array(seed[:3]))
        builder.free(km.array(seed[:3]))
        for j, i in enumerate((0, 1, 3)):
            builder.x(seed[3 + j])
            v[i] = seed[3 + j]
        b.seed_root_frame(builder, v, inverse=True)
        for i in (0, 1, 3):
            m = outcomes.pop(i)
            builder.push_condition(m); builder.z(v[i]); builder.pop_condition(); builder.free(m)
        assert all(d.consumed and not d.measurements for d in token.rows)
    return seed_cleanup


def apply(ctx):
    baseline = ctx.baseline
    lifecycle = ctx.components['lifecycle']

    def installed(builder, v, D, word, token, dirty):
        return product_inverse(builder, v, D, word, token, dirty, baseline=baseline)
    lifecycle.product_inverse = installed
    baseline.seed_cleanup = make_seed_cleanup(baseline)
