"""Reed-Solomon MBUC syndrome decoder built from divsteps (our own design, ADR-0009 stage 1).

Key equation by constant-time division-free steps (Bernstein-Yang "divsteps", the idea behind the paper's
"Dialog", arXiv:2510.10967 section II B 3) on the pair (f, g) = (1, S(z)). We never store f and g. After k
steps z^k g_k = u_g + v_g S and z^k f_k = u_f + v_f S. Empirically (tests, 3000 random cases per size)
deg u_g < k, so u_g is the truncation of v_g S and is not stored; only the sigma-side rows (v_g, v_f) are.
Constant terms come from the rows:

    g_k(0) = [z^k](v_g S)          (a short convolution with the read-only syndromes)
    f_k(0) = b                     (one register, changes only on a swap)

One step (all control flow is data independent):
    d = g_k(0);  sw = (delta > 0) and d != 0;  if sw: swap rows v_g, v_f and registers d, b; delta -> -delta
    c = d / b  (kept: the dialog);  v_g ^= c * v_f;  delta += 1;  v_f shifts up by z (relabelling).
After n = 2t steps v_g is sigma up to a nonzero scalar. The f row is shifted up by z only while its top
coefficient (index t) is zero: past that it is dead (every later discrepancy is zero for decodable syndromes),
so it is frozen instead of kept as shifted-out garbage (one `sh` bit per step). sigma is then normalised in
place by 1 / sigma_0 and Omega = sigma S mod z^t is computed in place in the syndrome registers S_0..S_{t-1}
(descending order); both are undone before the reverse pass.
Chien search and Forney give e_j = Omega(z_j) / sigma'(z_j) at z_j = alpha^-j,
and the phase is applied by `gf2_phase_by_product`. Division at the Forney step goes through the GF(2^6)
tower (`tower.py`). The dialog is erased by running the steps backwards; the discrepancy and `D = c b`
registers clear by measurement, so the reverse pass skips the convolution.

Valid for decodable syndromes (at most t = n // 2 errors), the benchmark contract. Register shapes are
static; only values depend on the input. Measured bounds: rows within t + 1 coefficients, delta in [-2, n+1].
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import kickmix as km  # type: ignore[import-not-found,unused-ignore]

from dqi_gen.tower import Tower, apply_matrix_inplace, xor_linear

OFFSET = 8  # delta is stored as delta + OFFSET (unsigned); delta > 0 <=> stored > OFFSET


def _cat(regs: Sequence[Any]) -> Any:
    return km.array([q for r in regs for q in r])


class DivstepDecoder:
    def __init__(self, n_syndromes: int, field: Any):
        if n_syndromes < 2 or n_syndromes % 2:
            raise ValueError(f"n_syndromes must be even and at least 2, got {n_syndromes}.")
        self.n = n_syndromes
        self.t = n_syndromes // 2
        self.gf = field
        self.deg = field.degree

    # ---- helpers -------------------------------------------------------------------------------

    def _alloc_regs(self, builder: Any, count: int) -> list[Any]:
        return [builder.alloc_qubits(self.deg) for _ in range(count)]

    def _negate_delta(self, builder: Any, delta: Any, ctrl: Any) -> None:
        """delta' -> 2 * OFFSET - delta' when ctrl (an involution): ~x + 2*OFFSET + 1 (mod 2^W)."""
        builder.cx(ctrl, delta)
        builder.iadd(2 * OFFSET + 1, target=delta, control=ctrl)

    def _sw_flags(self, builder: Any, delta: Any, d_reg: Any) -> tuple[Any, Any]:
        """Allocates and fills gt = (delta > 0) and nz = (D != 0). Free with `_unflag`."""
        gt = builder.alloc_qubits(1)[0]
        nz = builder.alloc_qubits(1)[0]
        builder.flip_if_greater_than(delta, OFFSET, target=gt)
        builder.flip_if_equal(d_reg, 0, target=nz)
        builder.x(nz)
        return gt, nz

    def _unflag(self, builder: Any, delta: Any, d_reg: Any, gt: Any, nz: Any) -> None:
        builder.x(nz)
        builder.flip_if_equal(d_reg, 0, target=nz)
        builder.flip_if_greater_than(delta, OFFSET, target=gt)
        builder.free(nz)
        builder.free(gt)

    # ---- one divstep, forward and backward -----------------------------------------------------

    def _forward_step(self, builder: Any, k: int, s: Sequence[Any], st: dict[str, Any]) -> None:
        t, gf = self.t, self.gf
        gv, fv, bb, delta = st["gv"], st["fv"], st["b"], st["delta"]
        with builder.mark("discrepancy"):
            d_reg = builder.alloc_qubits(self.deg)
            for i in range(min(t, k) + 1):
                builder.ixor_gf2_mul(gv[i], s[k - i], target=d_reg, field=gf)
        with builder.mark("swap_decision"):
            gt, nz = self._sw_flags(builder, delta, d_reg)
            sw = builder.alloc_qubits(1)[0]
            builder.init_and(gt, nz, sw)
            self._unflag(builder, delta, d_reg, gt, nz)
        with builder.mark("swap_rows"):
            builder.cswap(sw, d_reg, bb)
            builder.cswap(sw, _cat(gv[: t + 1]), _cat(fv[: t + 1]))
            self._negate_delta(builder, delta, sw)
            builder.iadd(1, target=delta)
        with builder.mark("quotient"):
            c = builder.init_gf2_div(d_reg, bb, field=gf)
        with builder.mark("row_update"):
            self._update_rows(builder, c, st)
        builder.del_gf2_mul(c, bb, target=d_reg, field=gf)
        builder.free(d_reg)
        with builder.mark("shift_f"):
            sh = builder.alloc_qubits(1)[0]
            self._shift_flag(builder, fv[t], sh)
            self._shift_f(builder, fv, sh)
        st["sh"].append(sh)
        st["c"].append(c)
        st["sw"].append(sw)

    @staticmethod
    def _shift_flag(builder: Any, top: Any, sh: Any) -> None:
        """sh ^= (top == 0). The f row is shifted up by z only while its top coefficient is zero."""
        ladder = DivstepDecoder._zero_test(builder, top)
        builder.cx(ladder[-1], sh)
        DivstepDecoder._zero_untest(builder, top, ladder)

    @staticmethod
    def _shift_f(builder: Any, fv: list[Any], sh: Any, *, inverse: bool = False) -> None:
        """Controlled cyclic shift of the t + 1 registers up by one (top coefficient is zero when sh).

        A row whose degree would pass t is dead: for decodable syndromes every later discrepancy is zero, so
        it is never read again; freezing it keeps the window at t + 1 registers instead of keeping the
        shifted-out coefficients as garbage.
        """
        t = len(fv) - 1
        order = range(t, 0, -1) if not inverse else range(1, t + 1)
        for i in order:
            builder.cswap(sh, fv[i], fv[i - 1])

    def _update_rows(self, builder: Any, c: Any, st: dict[str, Any]) -> None:
        t, gf = self.t, self.gf
        for i in range(t + 1):
            builder.ixor_gf2_mul(c, st["fv"][i], target=st["gv"][i], field=gf)

    def _backward_step(self, builder: Any, k: int, s: Sequence[Any], st: dict[str, Any]) -> None:
        t, gf = self.t, self.gf
        gv, fv, bb, delta = st["gv"], st["fv"], st["b"], st["delta"]
        c, sw = st["c"].pop(), st["sw"].pop()
        sh = st["sh"].pop()
        with builder.mark("shift_f"):
            self._shift_f(builder, fv, sh, inverse=True)
            self._shift_flag(builder, fv[t], sh)
            builder.free(sh)
        d_reg = builder.alloc_qubits(self.deg)
        builder.init_gf2_mul(c, bb, target=d_reg, field=gf)
        with builder.mark("row_update"):
            self._update_rows(builder, c, st)
        with builder.mark("quotient"):
            builder.del_gf2_div(d_reg, bb, target=c, field=gf)
        builder.free(c)
        with builder.mark("swap_rows"):
            builder.isub(1, target=delta)
            self._negate_delta(builder, delta, sw)
            builder.cswap(sw, _cat(gv[: t + 1]), _cat(fv[: t + 1]))
            builder.cswap(sw, d_reg, bb)
        with builder.mark("swap_decision"):
            gt, nz = self._sw_flags(builder, delta, d_reg)
            builder.del_and(gt, nz, sw)
            self._unflag(builder, delta, d_reg, gt, nz)
            builder.free(sw)
        with builder.mark("discrepancy_clear"):
            mask = builder.alloc_bits(self.deg)
            builder.hmr(d_reg, mask)
            for i in range(min(t, k) + 1):
                builder.gf2_phase_by_product(gv[i], s[k - i], mask=mask, field=gf)
            builder.free(mask)
            builder.free(d_reg)

    def _normalise(self, builder: Any, gv: list[Any], *, inverse: bool = False) -> Any:
        """Scales sigma by 1 / sigma_0 in place, keeping sigma_0 in gv[0] (the implicit leading 1).

        Each register x becomes y = mu x through an out-of-place product, and x is then cleared by
        measurement as lam * y (zero Toffolis); the register list is relabelled. Returns mu (12 qubits).
        """
        gf, lam = self.gf, gv[0]
        if not inverse:
            mu = builder.init_gf2_inverse(lam, field=gf)
            for k in range(1, self.t + 1):
                y = builder.init_gf2_mul(gv[k], mu, field=gf)
                builder.del_gf2_mul(lam, y, target=gv[k], field=gf)
                builder.free(gv[k])
                gv[k] = y
            return mu
        raise AssertionError("use _unnormalise")

    def _unnormalise(self, builder: Any, gv: list[Any], mu: Any) -> None:
        gf, lam = self.gf, gv[0]
        for k in range(1, self.t + 1):
            x = builder.init_gf2_mul(gv[k], lam, field=gf)
            builder.del_gf2_mul(mu, x, target=gv[k], field=gf)
            builder.free(gv[k])
            gv[k] = x
        builder.del_gf2_inverse(lam, target=mu, field=gf)
        builder.free(mu)

    def _omega(self, builder: Any, gv: list[Any], s: Sequence[Any]) -> None:
        """In place on the syndromes: S_i <- S_i + sum_{1<=k<=i} sigma_k S_{i-k} = Omega_i (i < t).

        Needs the normalised sigma (sigma_0 = 1). Descending i, so every S_{i-k} read is still original.
        The registers are restored by `_omega_undo`; no qubits are added.
        """
        for i in range(self.t - 1, -1, -1):
            for k in range(1, i + 1):
                builder.ixor_gf2_mul(gv[k], s[i - k], target=s[i], field=self.gf)

    def _omega_undo(self, builder: Any, gv: list[Any], s: Sequence[Any]) -> None:
        for i in range(self.t):
            for k in range(1, i + 1):
                builder.ixor_gf2_mul(gv[k], s[i - k], target=s[i], field=self.gf)

    @staticmethod
    def _zero_test(builder: Any, reg: Any) -> Any:
        """Ladder of ANDs of the negated bits of `reg`; the last qubit is (reg == 0). One Toffoli per bit."""
        builder.x(reg)
        anc = builder.alloc_qubits(len(reg) - 1)
        builder.init_and(reg[0], reg[1], anc[0])
        for i in range(2, len(reg)):
            builder.init_and(anc[i - 2], reg[i], anc[i - 1])
        return anc

    @staticmethod
    def _zero_untest(builder: Any, reg: Any, anc: Any) -> None:
        for i in range(len(reg) - 1, 1, -1):
            builder.del_and(anc[i - 2], reg[i], anc[i - 1])
        builder.del_and(reg[0], reg[1], anc[0])
        builder.free(anc)
        builder.x(reg)

    @staticmethod
    def _subfield_inverse(builder: Any, gf_h: Any) -> Any:
        """(compute, uncompute) of `ninv = x^-1` in GF(2^h). Even h goes through one more tower level."""
        h = gf_h.degree
        if h % 2 or h < 4:

            def compute_plain(x: Any) -> Any:
                ninv, chain = builder.init_gf2_inverse_with_scaffold(x, field=gf_h)
                return ninv, chain

            def uncompute_plain(x: Any, ninv: Any, state: Any) -> None:
                builder.del_gf2_inverse_with_scaffold(x, target=ninv, scaffold=state, field=gf_h)
                builder.free(state)
                builder.free(ninv)

            return compute_plain, uncompute_plain

        q = h // 2
        gf_q = km.GF2Field(q)
        tw = Tower.build(gf_h, gf_q)
        norm_b = [gf_q.mul(tw.b, gf_q.square(1 << i)) for i in range(q)]

        def compute(x: Any) -> Any:
            apply_matrix_inplace(builder, list(x), tw.to_tower)
            a_, b_ = x[:q], x[q:]
            norm = builder.init_gf2_mul(a_, b_, field=gf_q)
            xor_linear(builder, a_, norm, tw.square)
            xor_linear(builder, b_, norm, norm_b)
            ninv_q, chain = builder.init_gf2_inverse_with_scaffold(norm, field=gf_q)
            e_ = builder.alloc_qubits(q)
            builder.cx(a_, e_)
            builder.cx(b_, e_)
            ninv = builder.alloc_qubits(h)
            builder.init_gf2_mul(e_, ninv_q, target=ninv[:q], field=gf_q)
            builder.init_gf2_mul(b_, ninv_q, target=ninv[q:], field=gf_q)
            apply_matrix_inplace(builder, list(ninv), tw.from_tower)
            apply_matrix_inplace(builder, list(x), tw.from_tower)
            return ninv, (norm, ninv_q, chain, e_)

        def uncompute(x: Any, ninv: Any, state: Any) -> None:
            norm, ninv_q, chain, e_ = state
            apply_matrix_inplace(builder, list(x), tw.to_tower)
            a_, b_ = x[:q], x[q:]
            apply_matrix_inplace(builder, list(ninv), tw.to_tower)
            builder.del_gf2_mul(b_, ninv_q, target=ninv[q:], field=gf_q)
            builder.del_gf2_mul(e_, ninv_q, target=ninv[:q], field=gf_q)
            builder.cx(b_, e_)
            builder.cx(a_, e_)
            builder.free(e_)
            builder.del_gf2_inverse_with_scaffold(norm, target=ninv_q, scaffold=chain, field=gf_q)
            builder.free(chain)
            builder.free(ninv_q)
            xor_linear(builder, b_, norm, norm_b)
            xor_linear(builder, a_, norm, tw.square)
            builder.del_gf2_mul(a_, b_, target=norm, field=gf_q)
            builder.free(norm)
            apply_matrix_inplace(builder, list(x), tw.from_tower)
            builder.free(ninv)

        return compute, uncompute

    def _tower_ops(self, builder: Any) -> Any:
        """Phase kickback of <M, om / od> gated by z through the GF(2^6) tower; None for odd degrees.

        With od = A + B y and om = C + D y: om / od = om conj(od) / N, N = A^2 + A B + b B^2 in the subfield.
        Three subfield products give om conj(od) (Karatsuba); N^-1 is gated by z and folded into the phase
        by `gf2_phase_by_product`, so the only extra Toffolis are one norm product, one subfield inversion,
        the three products and the gating.
        """
        deg = self.deg
        if deg % 2:
            return None
        h = deg // 2
        gf_h = km.GF2Field(h)
        tw = Tower.build(self.gf, gf_h)
        norm_b = [gf_h.mul(tw.b, gf_h.square(1 << i)) for i in range(h)]
        inv_compute, inv_uncompute = self._subfield_inverse(builder, gf_h)

        def run(od: Any, om: Any, z: Any, mask: Any) -> None:
            apply_matrix_inplace(builder, list(od), tw.to_tower)
            a_, b_ = od[:h], od[h:]
            norm = builder.init_gf2_mul(a_, b_, field=gf_h)
            xor_linear(builder, a_, norm, tw.square)
            xor_linear(builder, b_, norm, norm_b)
            ninv, inv_state = inv_compute(norm)
            gated = builder.alloc_qubits(h)
            builder.init_and(z, ninv, gated)
            e_ = builder.alloc_qubits(h)
            builder.cx(a_, e_)
            builder.cx(b_, e_)
            rhs = builder.alloc_qubits(deg)
            builder.init_gf2_mul(e_, gated, target=rhs[:h], field=gf_h)
            builder.init_gf2_mul(b_, gated, target=rhs[h:], field=gf_h)
            apply_matrix_inplace(builder, list(rhs), tw.from_tower)
            builder.gf2_phase_by_product(om, rhs, mask=mask, field=self.gf)
            apply_matrix_inplace(builder, list(rhs), tw.to_tower)
            builder.del_gf2_mul(b_, gated, target=rhs[h:], field=gf_h)
            builder.del_gf2_mul(e_, gated, target=rhs[:h], field=gf_h)
            builder.free(rhs)
            builder.cx(b_, e_)
            builder.cx(a_, e_)
            builder.free(e_)
            builder.del_and(z, ninv, gated)
            builder.free(gated)
            inv_uncompute(norm, ninv, inv_state)
            xor_linear(builder, b_, norm, norm_b)
            xor_linear(builder, a_, norm, tw.square)
            builder.del_gf2_mul(a_, b_, target=norm, field=gf_h)
            builder.free(norm)
            apply_matrix_inplace(builder, list(od), tw.from_tower)

        return run

    # ---- Chien search and Forney with the MBUC phase -------------------------------------------

    def _chien_forney(self, builder: Any, gv: list[Any], gu: list[Any], error_mbuc: Sequence[Any]) -> None:
        t, gf, deg = self.t, self.gf, self.deg
        order = (1 << deg) - 1
        alpha = gf.primitive_element
        m = len(error_mbuc)
        steps = [(gv[k], gf.pow(alpha, (-k) % order)) for k in range(1, t + 1)]
        steps += [(gu[k], gf.pow(alpha, (-(k + 1)) % order)) for k in range(t)]
        steps = [(reg, c) for reg, c in steps if c != 1]
        sg, od, om = (builder.alloc_qubits(deg) for _ in range(3))
        inv = builder.alloc_qubits(deg)
        located = builder.alloc_qubits(deg)
        pairs = (
            [(gv[k], sg) for k in range(1, t + 1)]
            + [(gv[k], od) for k in range(1, t + 1, 2)]
            + [(gu[k], om) for k in range(t)]
        )
        src = _cat([p[0] for p in pairs])
        dst = _cat([p[1] for p in pairs])
        position = builder.mark("forney_position")
        tower = self._tower_ops(builder)
        for j in range(m):
            with position:
                builder.cx(src, dst)
                builder.x(sg[0])  # sigma_0 = 1 after normalisation (gv[0] holds the scale)
                ladder = self._zero_test(builder, sg)
                z = ladder[-1]
                if tower is None:
                    _, chain = builder.init_gf2_inverse_with_scaffold(od, target=inv, field=gf)
                    builder.init_and(z, om, located)
                    builder.gf2_phase_by_product(located, inv, mask=error_mbuc[j], field=gf)
                    builder.del_and(z, om, located)
                    builder.del_gf2_inverse_with_scaffold(od, target=inv, scaffold=chain, field=gf)
                    builder.free(chain)
                else:
                    tower(od, om, z, error_mbuc[j])
                self._zero_untest(builder, sg, ladder)
                builder.x(sg[0])
                builder.cx(src, dst)
                if j + 1 < m:
                    for reg, c in steps:
                        builder.gf2_imul(c, target=reg, field=gf)
        if m > 1:
            for reg, c in steps:
                builder.gf2_idiv(gf.pow(c, m - 1), target=reg, field=gf)
        for reg in (located, inv, sg, od, om):
            builder.free(reg)

    # ---- whole decoder -------------------------------------------------------------------------

    def build_syndrome_decoding_mbuc(
        self, builder: Any, *, syndromes: Sequence[Any], error_mbuc: Sequence[Any]
    ) -> None:
        n, t = self.n, self.t
        if len(syndromes) != n:
            raise ValueError(f"Expected {n} syndrome registers, got {len(syndromes)}.")
        if not n <= len(error_mbuc) <= (1 << self.deg) - 1:
            raise ValueError(f"Expected between {n} and {(1 << self.deg) - 1} error_mbuc registers.")
        width = (n + 2 * OFFSET + 2).bit_length() + 1
        st: dict[str, Any] = {
            "gv": self._alloc_regs(builder, t + 1),
            "fv": self._alloc_regs(builder, t + 1),
            "b": builder.alloc_qubits(self.deg),
            "delta": builder.alloc_qubits(width),
            "c": [],
            "sw": [],
            "sh": [],
        }
        init_ones = km.array([st["gv"][0][0], st["b"][0]])
        builder.x(init_ones)
        builder.iadd(OFFSET + 1, target=st["delta"])
        with builder.mark("forward_divsteps"):
            for k in range(n):
                self._forward_step(builder, k, syndromes, st)
        with builder.mark("omega"):
            mu = self._normalise(builder, st["gv"])
            self._omega(builder, st["gv"], syndromes)
        with builder.mark("chien_forney_mbuc"):
            self._chien_forney(builder, st["gv"], list(syndromes[:t]), error_mbuc)
        with builder.mark("omega_clear"):
            self._omega_undo(builder, st["gv"], syndromes)
            self._unnormalise(builder, st["gv"], mu)
        with builder.mark("reverse_divsteps"):
            for k in range(n - 1, -1, -1):
                self._backward_step(builder, k, syndromes, st)
        builder.isub(OFFSET + 1, target=st["delta"])
        builder.x(init_ones)
        for reg in (*st["gv"], *st["fv"], st["b"], st["delta"]):
            builder.free(reg)


def build_circuit(m: int, n: int, degree: int) -> Any:
    """Standalone decoder circuit with the registers the host verifier expects (S0.., E0..)."""
    builder = km.CircuitBuilder()
    syndromes = [builder.create_quantum_register(degree, name=f"S{i}") for i in range(n)]
    error_mbuc = [builder.create_classical_register(degree, name=f"E{j}") for j in range(m)]
    DivstepDecoder(n, km.GF2Field(degree)).build_syndrome_decoding_mbuc(
        builder, syndromes=syndromes, error_mbuc=error_mbuc
    )
    return builder.finish_circuit()
