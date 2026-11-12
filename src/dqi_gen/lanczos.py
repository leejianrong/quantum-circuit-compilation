"""Reed-Solomon MBUC syndrome decoder from a dialog-free Jacobi (Lanczos) solver (QCC-19).

Design, information argument and cost prediction: docs/experiments/dqi-inplace.md; classical reference:
`jacobi.py`. The state is the pair `(cur, prev) = (p_k, p_{k-1})` of monic orthogonal polynomials of the
moment functional `L(z^i) = S_i` plus one carried scalar `h`; the raw syndromes are erased in place as the
pair grows (`S_{k-1}` from `p_k`) and their qubits are reused for the polynomials. There is no dialog and no
Omega: the scan evaluates the Gauss weight `h / (p_{N-1}(x) * x p_N'(x))` at every position.

Every step is written once as a forward sequence of reversible operations on a `Tape`; the reverse pass
replays the inverses of the recorded operations (a product that was cleared by measurement comes back as a
product, and the other way round). Registers are `Reg` objects recycled through a pool of zero registers,
which includes the erased syndrome registers. After exhaustion (weight `w < t`: `h_w = 0`) the update is
gated so the arrays freeze at `(p_w, p_{w-1})` and the carried scalar stays `h_{w-1}`.

Failures (per shot, about `2^-12` per step, not repaired): `h_k = 0` before `k = w`. A zero constant term
of `p_k` is handled by erasing with `p_k / z` (a controlled shift).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import kickmix as km  # type: ignore[import-not-found,unused-ignore]

from dqi_gen.decoder import DivstepDecoder
from dqi_gen.gfmul import FastMul
from dqi_gen.tower import Tower, apply_matrix_inplace, xor_linear


class Reg:
    """A field register (or a single flag qubit) whose qubits never change identity."""

    def __init__(self, q: Any, name: str = "", own: bool = False) -> None:
        self.q = q
        self.name = name
        self.own = own  # the qubits were allocated by us (the host's syndrome qubits cannot be freed)

    def __getitem__(self, i: int) -> Any:
        return self.q[i]


class Tape:
    """Records reversible operations so the reverse pass can replay their inverses."""

    def __init__(self, builder: Any, gf: Any) -> None:
        self.b = builder
        self.gf = gf
        self.deg = gf.degree
        self.ops: list[tuple[Any, ...]] = []
        self.pool: list[Reg] = []
        self.fresh: list[Reg] = []
        self.fm = FastMul(builder, gf)
        self._tw: Any = None

    # ---- execution of one primitive and its inverse --------------------------------------------

    def _exec(self, op: tuple[Any, ...]) -> None:
        b, gf = self.b, self.gf
        kind = op[0]
        if kind == "xmul":
            self.fm.ixor_mul(op[1].q, op[2].q, op[3].q)
        elif kind == "delmul":
            b.del_gf2_mul(op[1].q, op[2].q, target=op[3].q, field=gf)
        elif kind == "iadd":
            if op[3] is None:
                b.gf2_iadd(op[1].q, target=op[2].q, field=gf)
            else:
                b.gf2_iadd(op[1].q, target=op[2].q, field=gf, control=op[3].q[0])
        elif kind == "x":
            b.x(op[1].q[op[2]])
        elif kind == "cx":
            b.cx(op[1].q[op[2]], op[3].q[op[4]])
        elif kind == "cswap":
            ctrl, a, c = op[1], op[2], op[3]
            b.cswap(ctrl.q[0], km.array([q for r in a for q in r.q]), km.array([q for r in c for q in r.q]))
        elif kind == "initinv":
            self._tower_inverse(op[1].q, op[2].q, clear=False)
        elif kind == "delinv":
            self._tower_inverse(op[1].q, op[2].q, clear=True)
        elif kind == "initdiv":  # target ^= a / b
            self._tower_div(op[1].q, op[2].q, op[3].q, clear=False)
        elif kind == "deldiv":
            self._tower_div(op[1].q, op[2].q, op[3].q, clear=True)
        elif kind == "dot":
            for lhs, rhs in op[2]:
                self.fm.ixor_mul(lhs.q, rhs.q, op[1].q)
        elif kind == "cleardot":
            mask = b.alloc_bits(self.deg)
            b.hmr(op[1].q, mask)
            for lhs, rhs in op[2]:
                b.gf2_phase_by_product(lhs.q, rhs.q, mask=mask, field=gf)
            b.free(mask)
        elif kind == "and":  # target bits = control AND source bits
            b.init_and(op[1].q[0], op[2].q, op[3].q)
        elif kind == "unand":
            b.del_and(op[1].q[0], op[2].q, op[3].q)
        elif kind == "flipeq":  # target ^= (reg == const)
            b.flip_if_equal(op[1].q, op[2], target=op[3].q[0])
        elif kind == "flipgt":
            b.flip_if_greater_than(op[1].q, op[2], target=op[3].q[0])
        elif kind == "addint":  # reg += value when control
            b.iadd(op[2], target=op[1].q, control=op[3].q[0])
        elif kind == "subint":
            b.isub(op[2], target=op[1].q, control=op[3].q[0])
        elif kind == "take":
            if op[1] in self.pool:
                self.pool.remove(op[1])
        elif kind == "give":
            self.pool.append(op[1])
        else:
            raise ValueError(kind)

    _INVERSE = {
        "xmul": "xmul",
        "iadd": "iadd",
        "x": "x",
        "cx": "cx",
        "cswap": "cswap",
        "dot": "cleardot",
        "cleardot": "dot",
        "delmul": "initmul",
        "initmul": "delmul",
        "initinv": "delinv",
        "delinv": "initinv",
        "initdiv": "deldiv",
        "deldiv": "initdiv",
        "and": "unand",
        "unand": "and",
        "flipeq": "flipeq",
        "flipgt": "flipgt",
        "addint": "subint",
        "subint": "addint",
        "take": "give",
        "give": "take",
    }

    # ---- inversion through the GF(2^6) tower (about 82 Toffolis forward, 46 to clear) ----

    def _lend(self) -> list[Reg]:
        """Frees the idle zero registers we allocated (not the host syndrome registers) as scratch room."""
        spare = [r for r in self.pool if r.own]
        for reg in spare:
            self.b.free(reg.q)
        return spare

    def _unlend(self, spare: list[Reg]) -> None:
        for reg in spare:
            reg.q = self.b.alloc_qubits(self.deg)

    def _tower_inverse(self, x: Any, out: Any, *, clear: bool) -> None:
        """`out ^= 1 / x` (or clear `out`, known to hold `1 / x`, by measurement); `x` is unchanged.

        x = A + B y, 1/x = (A + B + B y) / N with N = A^2 + A B + b B^2 in GF(2^6): one subfield product, one
        subfield inversion with scaffold, two subfield products; the scaffold is undone for free.
        """
        b, h = self.b, self.deg // 2
        if self._tw is None:
            gf_h = km.GF2Field(h)
            self._tw = (
                gf_h,
                Tower.build(self.gf, gf_h),
                DivstepDecoder._subfield_inverse(b, gf_h, True),
            )
        gf_h, tw, (inv_compute, inv_uncompute) = self._tw
        norm_b = [gf_h.mul(tw.b, gf_h.square(1 << i)) for i in range(h)]
        mul = DivstepDecoder._mul
        apply_matrix_inplace(b, list(x), tw.to_tower)
        a_, b_ = x[:h], x[h:]
        norm = mul(b, a_, b_, gf_h, fast=True)
        xor_linear(b, a_, norm, tw.square)
        xor_linear(b, b_, norm, norm_b)
        ninv, state = inv_compute(norm)
        b.cx(b_, a_)  # a_ holds A + B until the products are done
        e_ = a_
        if clear:
            apply_matrix_inplace(b, list(out), tw.to_tower)
            b.del_gf2_mul(b_, ninv, target=out[h:], field=gf_h)
            b.del_gf2_mul(e_, ninv, target=out[:h], field=gf_h)
        else:
            mul(b, e_, ninv, gf_h, out[:h], True)
            mul(b, b_, ninv, gf_h, out[h:], True)
            apply_matrix_inplace(b, list(out), tw.from_tower)
        b.cx(b_, a_)
        inv_uncompute(norm, ninv, state)
        xor_linear(b, b_, norm, norm_b)
        xor_linear(b, a_, norm, tw.square)
        b.del_gf2_mul(a_, b_, target=norm, field=gf_h)
        b.free(norm)
        apply_matrix_inplace(b, list(x), tw.from_tower)

    def _tower_div(self, a: Any, den: Any, target: Any, *, clear: bool) -> None:
        """`target ^= a / den`, or clear `target` known to hold it."""
        b = self.b
        inv = b.alloc_qubits(self.deg)
        self._tower_inverse(den, inv, clear=False)
        if clear:
            b.del_gf2_mul(a, inv, target=target, field=self.gf)
        else:
            self.fm.ixor_mul(a, inv, target)
        self._tower_inverse(den, inv, clear=True)
        b.free(inv)

    def _do(self, op: tuple[Any, ...]) -> None:
        if op[0] in ("take", "give"):
            self._exec(op)
            return
        spare = self._lend()  # idle zero registers of ours serve as scratch for this operation
        if op[0] == "initmul":  # init_gf2_mul resets the target first; the target is zero by construction
            self.fm.ixor_mul(op[1].q, op[2].q, op[3].q)
        else:
            self._exec(op)
        self._unlend(spare)

    def emit(self, *op: Any) -> None:
        self.ops.append(op)
        self._do(op)

    def undo(self, start: int, end: int) -> None:
        for op in reversed(self.ops[start:end]):
            self._do((self._INVERSE[op[0]], *op[1:]))

    # ---- register pool ---------------------------------------------------------------------------

    def take(self) -> Reg:
        if self.pool:
            reg = self.pool[-1]
        else:
            reg = Reg(self.b.alloc_qubits(self.deg), f"r{len(self.fresh)}", own=True)
            self.fresh.append(reg)
        self.emit("take", reg)
        return reg

    def give(self, reg: Reg) -> None:
        self.emit("give", reg)

    # ---- recorded operations ---------------------------------------------------------------------

    def xmul(self, lhs: Reg, rhs: Reg, target: Reg) -> None:
        self.emit("xmul", lhs, rhs, target)

    def delmul(self, lhs: Reg, rhs: Reg, target: Reg) -> None:
        self.emit("delmul", lhs, rhs, target)

    def iadd(self, src: Reg, dst: Reg, ctrl: Reg | None = None) -> None:
        self.emit("iadd", src, dst, ctrl)

    def x(self, reg: Reg, i: int = 0) -> None:
        self.emit("x", reg, i)

    def cx(self, c: Reg, ci: int, t: Reg, ti: int) -> None:
        self.emit("cx", c, ci, t, ti)

    def cswap(self, ctrl: Reg, a: Sequence[Reg], c: Sequence[Reg]) -> None:
        self.emit("cswap", ctrl, tuple(a), tuple(c))

    def dot(self, target: Reg, pairs: Sequence[tuple[Reg, Reg]]) -> None:
        self.emit("dot", target, tuple(pairs))

    def cleardot(self, target: Reg, pairs: Sequence[tuple[Reg, Reg]]) -> None:
        self.emit("cleardot", target, tuple(pairs))

    def init_inv(self, src: Reg) -> Reg:
        out = self.take()
        self.emit("initinv", src, out)
        return out

    def del_inv(self, src: Reg, out: Reg) -> None:
        self.emit("delinv", src, out)
        self.give(out)

    def init_inv_scaffold(self, src: Reg) -> tuple[Reg, list[Any]]:
        return self.init_inv(src), []

    def del_inv_scaffold(self, src: Reg, out: Reg, holder: list[Any]) -> None:
        self.del_inv(src, out)

    def init_mul(self, lhs: Reg, rhs: Reg) -> Reg:
        out = self.take()
        self.emit("initmul", lhs, rhs, out)  # the reverse pass clears it by measurement
        return out

    def and_bits(self, ctrl: Reg, src: Reg) -> Reg:
        out = self.take()
        self.emit("and", ctrl, src, out)
        return out

    def unand_bits(self, ctrl: Reg, src: Reg, out: Reg) -> None:
        self.emit("unand", ctrl, src, out)
        self.give(out)


class LanczosDecoder:
    def __init__(self, n_syndromes: int, field: Any):
        if n_syndromes < 4 or n_syndromes % 2:
            raise ValueError(f"n_syndromes must be even and at least 4, got {n_syndromes}.")
        self.n = n_syndromes
        self.t = n_syndromes // 2
        self.gf = field
        self.deg = field.degree
        self.helper = DivstepDecoder(n_syndromes, field)

    # ---- one step, forward ------------------------------------------------------------------------

    def _step(self, tp: Tape, k: int, s: list[Reg], st: dict[str, Any]) -> None:
        cur: list[Reg] = st["cur"]
        prev: list[Reg] = st["prev"]
        h_prev: Reg = st["h"]
        inv_prev: Reg = st["inv"]
        al, cnt = st["al"], st["cnt"]
        # A. erase S_{k-1} from p_k (valid while p_k(0) != 0)
        if k >= 1:
            z0 = st["z0"]  # p_k(0) == 0 (about 2^-12): erase with p_k / z instead (valid for k >= 2)
            tp.emit("flipeq", cur[0], 0, z0)
            for i in range(k):
                tp.cswap(z0, [cur[i]], [cur[i + 1]])
            inv0, scaffold = tp.init_inv_scaffold(cur[0])
            acc = tp.take()
            pairs = [(cur[i], s[k - 1 + i]) for i in range(1, k + 1)]
            tp.dot(acc, pairs)
            tp.delmul(acc, inv0, s[k - 1])
            tp.cleardot(acc, pairs)
            tp.give(acc)
            tp.del_inv_scaffold(cur[0], inv0, scaffold)
            for i in reversed(range(k)):
                tp.cswap(z0, [cur[i]], [cur[i + 1]])
            tp.emit("flipeq", cur[0], 0, z0)
            tp.give(s[k - 1])
        # B. capacity for p_{k+1}
        cur.append(tp.take())
        prev.append(tp.take())
        # C. heads
        h = tp.take()
        hp = [(cur[i], s[k + i]) for i in range(k + 1)]
        tp.dot(h, hp)
        # D. alive = (h != 0)
        tp.emit("flipeq", h, 0, al)
        tp.x(al)
        # E. a0 = s / h, then clear s through s = a0 * h (s is taken after the inversion: lower peak)
        inv_h = tp.init_inv(h)
        sh = tp.take()
        sp = [(cur[i], s[k + 1 + i]) for i in range(k + 1)]
        tp.dot(sh, sp)
        a0 = tp.init_mul(sh, inv_h)
        tp.delmul(a0, h, sh)
        tp.give(sh)
        # F. b = h / h_prev
        b = tp.init_mul(h, inv_prev)
        # H. lam = 1 / b_eff
        lam = tp.init_mul(h_prev, inv_h)
        tp.x(al)
        tp.cx(al, 0, b, 0)
        tp.cx(al, 0, lam, 0)
        tp.x(al)
        # I. dead: swap arrays so that prev (to be rewritten) holds p_k
        tp.x(al)
        tp.cswap(al, cur, prev)
        tp.x(al)
        # J. prev <- b_eff * prev in place
        for i in range(k):
            y = tp.take()
            tp.emit("initmul", b, prev[i], y)
            tp.delmul(lam, y, prev[i])
            old, prev[i] = prev[i], y
            tp.give(old)
        tp.x(al)
        tp.cx(al, 0, b, 0)
        tp.cx(al, 0, lam, 0)
        tp.x(al)
        # L. carried scalars: alive -> (h, inv_h), dead -> keep (h_prev, inv_prev)
        tp.x(al)
        tp.cswap(al, [h, inv_h], [h_prev, inv_prev])
        tp.x(al)
        tp.delmul(lam, h, h_prev)  # lam = h_{k-1} / h_k = 1 / b
        tp.give(h_prev)
        tp.emit("delinv", b, lam)
        tp.give(lam)
        tp.delmul(b, inv_h, inv_prev)
        tp.give(inv_prev)
        st["h"], st["inv"] = h, inv_h
        # G (after J, lower peak). a = a0 + p_{k,k-1} gated by alive
        if k >= 1:
            tp.iadd(cur[k - 1], a0)
        a_eff = tp.and_bits(al, a0)
        if k >= 1:
            tp.iadd(cur[k - 1], a0)
        # K. prev += (alive * z + a_eff) * cur
        for i in range(k + 1):
            tp.xmul(a_eff, cur[i], prev[i])
            tp.iadd(cur[i], prev[i + 1], al)
        cur, prev = prev, cur
        st["cur"], st["prev"] = cur, prev
        # M. clear b through the polynomials, then a_eff, a0, and the alive flag
        if k >= 1:
            tp.iadd(cur[k - 1], b, al)
            if k >= 2:
                tp.iadd(prev[k - 2], b, al)
            tp.xmul(a_eff, prev[k - 1], b)
        tp.give(b)
        if k >= 1:
            tp.iadd(prev[k - 1], cur[k])
        tp.unand_bits(al, cur[k], a_eff)
        if k >= 1:
            tp.iadd(prev[k - 1], cur[k])
        tp.iadd(cur[k], a0, al)
        tp.give(a0)
        tp.emit("addint", cnt, 1, al)
        tp.emit("flipgt", cnt, k, al)

    # ---- scan ------------------------------------------------------------------------------------

    def _scan(self, builder: Any, st: dict[str, Any], error_mbuc: Sequence[Any]) -> None:
        gf, deg = self.gf, self.deg
        order = (1 << deg) - 1
        alpha = gf.primitive_element
        cur: list[Reg] = st["cur"]
        prev: list[Reg] = st["prev"]
        h: Reg = st["h"]
        m = len(error_mbuc)
        steps = [(cur[i].q, gf.pow(alpha, i % order)) for i in range(2, len(cur))]
        steps += [(cur[1].q, alpha)]
        steps += [(prev[i].q, gf.pow(alpha, i % order)) for i in range(1, len(prev))]
        tower = self.helper._tower_ops(builder, fast=True)
        if tower is None:
            raise ValueError("the Lanczos scan needs an even field degree")
        position = builder.mark("scan_position")
        fm = FastMul(builder, gf)

        def copies() -> tuple[Any, Any, Any, Any, Any]:
            """Zero accumulators `sg` (p_N), `od` (odd part), `am` (p_{N-1}) and their CNOT networks."""
            sg, od, am = (builder.alloc_qubits(deg) for _ in range(3))
            pairs = [(r.q, sg) for r in cur]
            pairs += [(cur[i].q, od) for i in range(1, len(cur), 2)]
            pairs += [(r.q, am) for r in prev]
            src = km.array([q for p in pairs for q in p[0]])
            dst = km.array([q for p in pairs for q in p[1]])
            return sg, od, am, src, dst

        # The accumulators are CNOT copies of the step registers, so they are released while the tower
        # computation runs and rebuilt, at no Toffoli cost, to clear the product and the zero test.
        for j in range(m):
            with position:
                sg, od, am, src, dst = copies()
                builder.cx(src, dst)
                ladder = self.helper._zero_test(builder, sg)
                z = ladder[-1]
                u = builder.alloc_qubits(deg)
                fm.ixor_mul(am, od, u)
                builder.x(sg)
                builder.cx(src, dst)
                for reg in (sg, od, am):
                    builder.free(reg)
                tower(u, h.q, z, error_mbuc[j])
                sg, od, am, src, dst = copies()
                builder.cx(src, dst)
                builder.x(sg)
                builder.del_gf2_mul(am, od, target=u, field=gf)
                builder.free(u)
                self.helper._zero_untest(builder, sg, ladder)
                builder.cx(src, dst)
                for reg in (sg, od, am):
                    builder.free(reg)
                if j + 1 < m:
                    for reg, c in steps:
                        builder.gf2_imul(c, target=reg, field=gf)
        if m > 1:
            for reg, c in steps:
                builder.gf2_idiv(gf.pow(c, m - 1), target=reg, field=gf)

    # ---- whole decoder ---------------------------------------------------------------------------

    def build_syndrome_decoding_mbuc(
        self, builder: Any, *, syndromes: Sequence[Any], error_mbuc: Sequence[Any]
    ) -> None:
        n, t = self.n, self.t
        if len(syndromes) != n:
            raise ValueError(f"Expected {n} syndrome registers, got {len(syndromes)}.")
        tp = Tape(builder, self.gf)
        s = [Reg(r, f"S{i}") for i, r in enumerate(syndromes)]
        al = Reg(builder.alloc_qubits(1), "al")
        z0 = Reg(builder.alloc_qubits(1), "z0")
        cnt = Reg(builder.alloc_qubits((t + 1).bit_length()), "cnt")
        one = tp.take()
        tp.x(one, 0)
        zero_h, zero_inv, zero_prev = tp.take(), tp.take(), tp.take()
        st: dict[str, Any] = {
            "cur": [one],
            "prev": [zero_prev],
            "h": zero_h,
            "inv": zero_inv,
            "al": al,
            "z0": z0,
            "cnt": cnt,
        }
        snaps: list[tuple[int, int, dict[str, Any]]] = []
        with builder.mark("forward_steps"):
            for k in range(t):
                snap = {key: (list(v) if isinstance(v, list) else v) for key, v in st.items()}
                start = len(tp.ops)
                self._step(tp, k, s, st)
                snaps.append((start, len(tp.ops), snap))
        with builder.mark("scan"):
            spare = [r for r in tp.pool if r.own]  # zero registers: lend their qubits to the scan
            for reg in spare:
                builder.free(reg.q)
            self._scan(builder, st, error_mbuc)
            for reg in spare:
                reg.q = builder.alloc_qubits(self.deg)
        with builder.mark("reverse_steps"):
            for start, end, snap in reversed(snaps):
                tp.undo(start, end)
                st = snap
        tp.x(one, 0)
        for reg in (one, zero_prev, zero_h, zero_inv):
            tp.emit("give", reg)
        for reg in tp.pool:
            if reg.own:
                builder.free(reg.q)
        builder.free(al.q)
        builder.free(z0.q)
        builder.free(cnt.q)


def build_circuit(m: int, n: int, degree: int) -> Any:
    """Standalone decoder circuit with the registers the host verifier expects (S0.., E0..)."""
    builder = km.CircuitBuilder()
    syndromes = [builder.create_quantum_register(degree, name=f"S{i}") for i in range(n)]
    error_mbuc = [builder.create_classical_register(degree, name=f"E{j}") for j in range(m)]
    LanczosDecoder(n, km.GF2Field(degree)).build_syndrome_decoding_mbuc(
        builder, syndromes=syndromes, error_mbuc=error_mbuc
    )
    return builder.finish_circuit()
