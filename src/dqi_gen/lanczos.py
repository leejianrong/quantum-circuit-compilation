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


class Reg:
    """A field register (or a single flag qubit) whose qubits never change identity."""

    def __init__(self, q: Any, name: str = "") -> None:
        self.q = q
        self.name = name

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

    # ---- execution of one primitive and its inverse --------------------------------------------

    def _exec(self, op: tuple[Any, ...]) -> None:
        b, gf = self.b, self.gf
        kind = op[0]
        if kind == "xmul":
            b.ixor_gf2_mul(op[1].q, op[2].q, target=op[3].q, field=gf)
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
            b.init_gf2_inverse(op[1].q, target=op[2].q, field=gf)
        elif kind == "delinv":
            b.del_gf2_inverse(op[1].q, target=op[2].q, field=gf)
        elif kind == "initdiv":
            b.init_gf2_div(op[1].q, op[2].q, target=op[3].q, field=gf)
        elif kind == "deldiv":
            b.del_gf2_div(op[1].q, op[2].q, target=op[3].q, field=gf)
        elif kind == "dot":
            for lhs, rhs in op[2]:
                b.ixor_gf2_mul(lhs.q, rhs.q, target=op[1].q, field=gf)
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

    def _do(self, op: tuple[Any, ...]) -> None:
        if op[0] == "initmul":  # init_gf2_mul resets the target first; the target is zero by construction
            self.b.ixor_gf2_mul(op[1].q, op[2].q, target=op[3].q, field=self.gf)
        else:
            self._exec(op)

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
            reg = Reg(self.b.alloc_qubits(self.deg), f"r{len(self.fresh)}")
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

    def init_mul(self, lhs: Reg, rhs: Reg) -> Reg:
        out = self.take()
        self.xmul(lhs, rhs, out)
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
            inv0 = tp.init_inv(cur[0])
            acc = tp.take()
            pairs = [(cur[i], s[k - 1 + i]) for i in range(1, k + 1)]
            tp.dot(acc, pairs)
            tp.xmul(acc, inv0, s[k - 1])
            tp.cleardot(acc, pairs)
            tp.give(acc)
            tp.del_inv(cur[0], inv0)
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
        sh = tp.take()
        sp = [(cur[i], s[k + 1 + i]) for i in range(k + 1)]
        tp.dot(sh, sp)
        # D. alive = (h != 0)
        tp.emit("flipeq", h, 0, al)
        tp.x(al)
        # E. a0 = s / h, then clear s through s = a0 * h
        inv_h = tp.init_inv(h)
        a0 = tp.init_mul(sh, inv_h)
        tp.delmul(a0, h, sh)
        tp.give(sh)
        # F. b = h / h_prev
        b = tp.init_mul(h, inv_prev)
        # G. a = a0 + p_{k,k-1} gated by alive
        if k >= 1:
            tp.iadd(cur[k - 1], a0)
        a_eff = tp.and_bits(al, a0)
        if k >= 1:
            tp.iadd(cur[k - 1], a0)
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
            tp.xmul(b, prev[i], y)
            tp.delmul(lam, y, prev[i])
            old, prev[i] = prev[i], y
            tp.give(old)
        tp.x(al)
        tp.cx(al, 0, b, 0)
        tp.cx(al, 0, lam, 0)
        tp.x(al)
        tp.delmul(h_prev, inv_h, lam)
        tp.give(lam)
        # K. prev += (alive * z + a_eff) * cur
        for i in range(k + 1):
            tp.xmul(a_eff, cur[i], prev[i])
            tp.iadd(cur[i], prev[i + 1], al)
        cur, prev = prev, cur
        st["cur"], st["prev"] = cur, prev
        # L. carried scalars: alive -> (h, inv_h), dead -> keep (h_prev, inv_prev)
        tp.x(al)
        tp.cswap(al, [h, inv_h], [h_prev, inv_prev])
        tp.x(al)
        tp.emit("deldiv", h, b, h_prev)
        tp.give(h_prev)
        tp.delmul(b, inv_h, inv_prev)
        tp.give(inv_prev)
        st["h"], st["inv"] = h, inv_h
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
        sg, od, am = (builder.alloc_qubits(deg) for _ in range(3))
        tower = self.helper._tower_ops(builder)
        if tower is None:
            raise ValueError("the Lanczos scan needs an even field degree")
        pairs_sg = [(r.q, sg) for r in cur]
        pairs_od = [(cur[i].q, od) for i in range(1, len(cur), 2)]
        pairs_am = [(r.q, am) for r in prev]
        src = km.array([q for p in pairs_sg + pairs_od + pairs_am for q in p[0]])
        dst = km.array([q for p in pairs_sg + pairs_od + pairs_am for q in p[1]])
        position = builder.mark("scan_position")
        for j in range(m):
            with position:
                builder.cx(src, dst)
                ladder = self.helper._zero_test(builder, sg)
                z = ladder[-1]
                u = builder.init_gf2_mul(am, od, field=gf)
                tower(u, h.q, z, error_mbuc[j])
                builder.del_gf2_mul(am, od, target=u, field=gf)
                builder.free(u)
                self.helper._zero_untest(builder, sg, ladder)
                builder.cx(src, dst)
                if j + 1 < m:
                    for reg, c in steps:
                        builder.gf2_imul(c, target=reg, field=gf)
        if m > 1:
            for reg, c in steps:
                builder.gf2_idiv(gf.pow(c, m - 1), target=reg, field=gf)
        for reg in (sg, od, am):
            builder.free(reg)

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
            self._scan(builder, st, error_mbuc)
        with builder.mark("reverse_steps"):
            for start, end, snap in reversed(snaps):
                tp.undo(start, end)
                st = snap
        tp.x(one, 0)
        for reg in (one, zero_prev, zero_h, zero_inv):
            tp.emit("give", reg)
        for reg in tp.pool:
            if reg in tp.fresh:
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
