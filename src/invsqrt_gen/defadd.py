"""Deferred-phase adder pair (QCC-13): our own derivation, after watching the reference circuit's adders.

`ripple_add` keeps `m - 2` carries alive, one per bit. The pair here needs far fewer:

* `fd_add` (forward): the carries are computed one after the other on two alternating wires and each carry
  is measured (X basis) as soon as the next one exists. The phase `(-1)^(m_j c_j)` of every measurement is
  not repaired: the outcome bit `m_j` is returned and the debt stays pending. Cost: `m - 1` Toffolis.
* `md_add` (the exact inverse, `t -= a + cin`): it recomputes the same carries (the borrows of the
  subtraction equal the carries of the addition) and pays each pending debt with a free conditional `Z` on
  the recomputed carry. With `split = s` the carry chain is cut at carry `c_s`: the low `s` bits are finished
  with the usual measured clean-up (all their carries alive), `c_s` is kept as the carry-in of the upper
  bits, and at the end `c_s` is measured with its own pending debt, which is paid inside a `PUSH_CONDITION`
  block by recomputing the low carries again (executed on half of the shots). At most `max(s, m - s)`
  carries are alive instead of `m - 2`.

The forward pair must be used as a pair: `md_add(.., ms)` with the bits `ms` that `fd_add` returned for the
same operands. Everything is checked against integers and for a clean global phase on every shot in the tests.
"""

import kickmix as km  # type: ignore[import-not-found,unused-ignore]


def fd_add(b: km.CircuitBuilder, a: km.array, t: km.array, cin: km.q | None = None) -> list[km.b]:
    """`t += a + cin` modulo `2^len(t)` with two alternating carry wires; returns the pending outcome bits.

    `bits[j - 1]` belongs to carry `c_j`, the carry into bit `j`, `j = 1 .. m - 2` (the carry into the
    top bit is xored straight into it, as in `ripple_add`).
    """
    m = len(t)
    if len(a) > m:
        a = a[:m]
    w = len(a)
    bits: list[km.b] = []
    pool = b.alloc_qubits(2) if m > 2 else km.array([])
    ci = cin
    owned = False  # whether `ci` is one of our carry wires (to be measured)

    def measure(q: km.q) -> None:
        bit = b.alloc_bits(1)
        b.hmr(km.array([q]), bit)
        bits.append(bit[0])

    for i in range(m - 2):
        new = pool[i % 2]
        if i < w:
            if ci is not None:
                b.cx(ci, a[i])
                b.cx(ci, t[i])
            b.init_and(a[i], t[i], new)
            if ci is not None:
                b.cx(ci, new)
                b.cx(ci, a[i])
            b.cx(a[i], t[i])
        else:
            assert ci is not None
            b.init_and(ci, t[i], new)
            b.cx(ci, t[i])
        if owned:
            assert ci is not None
            measure(ci)
        ci = new
        owned = True
    j, top = m - 2, m - 1
    if top < w:
        b.cx(a[top], t[top])
    if j < w:
        if ci is not None:
            b.cx(ci, a[j])
            b.cx(ci, t[j])
        b.ccx(a[j], t[j], t[top])
        if ci is not None:
            b.cx(ci, t[top])
            b.cx(ci, t[j])
            b.cx(ci, a[j])
        b.cx(a[j], t[j])
    else:
        assert ci is not None
        b.ccx(ci, t[j], t[top])
    if ci is not None:
        b.cx(ci, t[j])
    if owned:
        assert ci is not None
        measure(ci)
    if m > 2:
        b.free(pool)
    return bits


def md_add(
    b: km.CircuitBuilder,
    a: km.array,
    t: km.array,
    ms: list[km.b],
    cin: km.q | None = None,
    split: int | None = None,
) -> None:
    """The inverse of `fd_add(a, t, cin)`: `t -= a + cin`, paying the pending debts `ms` it returned.

    `split` (1 <= split <= m - 2) cuts the carry chain after carry `c_split` (see the module docstring).
    """
    m = len(t)
    if len(a) > m:
        a = a[:m]
    w = len(a)
    n_c = max(0, m - 2)
    assert len(ms) == n_c
    s = split if split is not None and 1 <= split <= n_c else n_c
    b.x(t)  # t - a = ~(~t + a): add `a` to the complemented target; its carries are the forward carries
    low = b.alloc_qubits(s) if s else km.array([])
    high: list[km.q] = []  # allocated after the low block is cleaned up (at most max(s, m - s) carries alive)

    def car(j: int) -> km.q:  # carry c_j, the carry into bit j, 1 <= j <= n_c
        return low[j - 1] if j <= s else high[j - s - 1]

    def carry_in(i: int) -> km.q | None:
        return car(i) if i else cin

    def up(i: int) -> None:
        ci = carry_in(i)
        c = car(i + 1)
        if i < w:
            if ci is not None:
                b.cx(ci, a[i])
                b.cx(ci, t[i])
            b.init_and(a[i], t[i], c)
            if ci is not None:
                b.cx(ci, c)
        else:
            assert ci is not None
            b.init_and(ci, t[i], c)
        b.push_condition(ms[i])  # the forward measured this carry: pay its debt on the new value
        b.z(c)
        b.pop_condition()

    def down(i: int) -> None:
        ci = carry_in(i)
        c = car(i + 1)
        if i < w:
            if ci is not None:
                b.cx(ci, c)
            b.del_and(a[i], t[i], c)
            if ci is not None:
                b.cx(ci, a[i])
            b.cx(a[i], t[i])
        else:
            assert ci is not None
            b.del_and(ci, t[i], c)
            b.cx(ci, t[i])

    for i in range(s):
        up(i)
    if s < n_c:
        # finish the low bits: bit s-1 keeps the boundary carry c_s, the rest are cleaned up
        ci = carry_in(s - 1)
        if s - 1 < w:
            if ci is not None:
                b.cx(ci, a[s - 1])
            b.cx(a[s - 1], t[s - 1])
        else:
            assert ci is not None
            b.cx(ci, t[s - 1])
        for i in range(s - 2, -1, -1):
            down(i)
        if s > 1:
            b.free(km.array(list(low)[: s - 1]))
        high.extend(b.alloc_qubits(n_c - s))
        for i in range(s, n_c):
            up(i)
    j, top = m - 2, m - 1
    ci = carry_in(j) if n_c else cin
    if top < w:
        b.cx(a[top], t[top])
    if j < w:
        if ci is not None:
            b.cx(ci, a[j])
            b.cx(ci, t[j])
        b.ccx(a[j], t[j], t[top])
        if ci is not None:
            b.cx(ci, t[top])
            b.cx(ci, t[j])
            b.cx(ci, a[j])
        b.cx(a[j], t[j])
    else:
        assert ci is not None
        b.ccx(ci, t[j], t[top])
    if ci is not None:
        b.cx(ci, t[j])
    if s < n_c:
        for i in range(n_c - 1, s - 1, -1):
            down(i)
        b.free(km.array(high))
        # the boundary carry c_s: measured with a pending debt, paid by recomputing the low carries
        # on half the shots
        bit = b.alloc_bits(1)
        b.hmr(km.array([low[s - 1]]), bit)
        b.free(km.array([low[s - 1]]))
        b.push_condition(bit[0])
        rep = b.alloc_qubits(s)
        for i in range(s):
            ci = cin if i == 0 else rep[i - 1]
            if i < w:
                b.cx(a[i], t[i])
                if ci is not None:
                    b.cx(ci, a[i])
                b.init_and(a[i], t[i], rep[i])
                if ci is not None:
                    b.cx(ci, rep[i])
            else:
                assert ci is not None
                b.cx(ci, t[i])
                b.init_and(ci, t[i], rep[i])
        b.z(rep[s - 1])
        for i in range(s - 1, -1, -1):
            ci = cin if i == 0 else rep[i - 1]
            if i < w:
                if ci is not None:
                    b.cx(ci, rep[i])
                b.del_and(a[i], t[i], rep[i])
                if ci is not None:
                    b.cx(ci, a[i])
                b.cx(a[i], t[i])
            else:
                assert ci is not None
                b.del_and(ci, t[i], rep[i])
                b.cx(ci, t[i])
        b.free(rep)
        b.pop_condition()
    else:
        for i in range(n_c - 1, -1, -1):
            down(i)
        b.free(low)
    b.x(t)
