"""Dialog-free Berlekamp-Massey (divstep) syndrome decoder (QCC-19, E030; ADR-0009 stage 2).

Our divstep decoder (`decoder.py`) stored a 12-bit quotient, a swap bit and a freeze bit per step
(945 qubits). Here the quotient and swap bit are recomputed, after the published idea of
Berlekamp-Massey with an invariant (Gu, Kemeny, Yelin, Lukin, arXiv:2610.22367 SI I.1). The
construction is our own, derived for our rows and checked classically in `bmref.py`:

* the swap rule is "swap when delta >= 0 and d != 0" (ties replace), so generic inputs never take a
  retain step;
* the invariant `g[0] * b = 1` holds and the shifted template has `f[0] = 0`, so a swap step is
  recognised from the after-state by `f[0] != 0` and its quotient is `c = 1 / (f[0] * b)`:
  computed, never stored;
* a retain step (no swap, `d != 0`) leaves no trace; its quotient goes on a stack of capacity one
  with the step index (a second retain step is a circuit failure, about 1e-4 of shots);
* the freeze bit `sh` of the template row is kept (35 bits, steps past `t`).

Everything after the forward pass (normalisation, Omega in place, Chien search with Forney, their
undoing) is shared with `DivstepDecoder`.
"""

from __future__ import annotations

from typing import Any

import kickmix as km  # type: ignore[import-not-found,unused-ignore]

from dqi_gen.decoder import OFFSET, DivstepDecoder, _cat
from dqi_gen.gfmul import FastMul
from dqi_gen.tower import Tower, apply_matrix_inplace, xor_linear


class BMDecoder(DivstepDecoder):
    _fm: FastMul | None = None
    margin = (
        1  # coefficients above ceil((k + 1) / 2) + margin are assumed zero (measured: excess is always 1)
    )
    _tw: Any = None

    # ---- products and inversions through the rank-42 multiplier and the GF(2^6) tower --------------

    def _width(self, k: int) -> int:
        """Registers of each row that step `k` touches: the locator degree is about `k / 2`."""
        full = min(self.t, k) + 1
        return int(full if self.margin < 0 else min(full, (k + 2) // 2 + self.margin))

    @property
    def _fast(self) -> bool:
        return int(self.deg) % 6 == 0

    def _xm(self, builder: Any, a: Any, b: Any, target: Any) -> None:
        """`target ^= a * b`, with the low-rank multiplier when the field has one."""
        if self._fm is None:
            try:
                self._fm = FastMul(builder, self.gf)
            except ValueError:
                self._fm = False  # type: ignore[assignment]
        if self._fm:
            self._fm.ixor_mul(a, b, target)
        else:
            builder.ixor_gf2_mul(a, b, target=target, field=self.gf)

    def _tinv(self, builder: Any, x: Any, out: Any, *, clear: bool) -> None:
        """`out ^= 1 / x` (or clear `out`, known to hold `1 / x`, by measurement); `x` is unchanged.

        x = A + B y, 1 / x = (A + B + B y) / N with N = A^2 + A B + b B^2 in GF(2^6).
        """
        h = self.deg // 2
        if self._tw is None:
            gf_h = km.GF2Field(h)
            self._tw = (gf_h, Tower.build(self.gf, gf_h), self._subfield_inverse(builder, gf_h, True))
        gf_h, tw, (inv_compute, inv_uncompute) = self._tw
        norm_b = [gf_h.mul(tw.b, gf_h.square(1 << i)) for i in range(h)]
        mul = self._mul
        apply_matrix_inplace(builder, list(x), tw.to_tower)
        a_, b_ = x[:h], x[h:]
        norm = mul(builder, a_, b_, gf_h, fast=True)
        xor_linear(builder, a_, norm, tw.square)
        xor_linear(builder, b_, norm, norm_b)
        ninv, state = inv_compute(norm)
        builder.cx(b_, a_)
        if clear:
            apply_matrix_inplace(builder, list(out), tw.to_tower)
            builder.del_gf2_mul(b_, ninv, target=out[h:], field=gf_h)
            builder.del_gf2_mul(a_, ninv, target=out[:h], field=gf_h)
        else:
            mul(builder, a_, ninv, gf_h, out[:h], True)
            mul(builder, b_, ninv, gf_h, out[h:], True)
            apply_matrix_inplace(builder, list(out), tw.from_tower)
        builder.cx(b_, a_)
        inv_uncompute(norm, ninv, state)
        xor_linear(builder, b_, norm, norm_b)
        xor_linear(builder, a_, norm, tw.square)
        builder.del_gf2_mul(a_, b_, target=norm, field=gf_h)
        builder.free(norm)
        apply_matrix_inplace(builder, list(x), tw.from_tower)

    def _update_rows(self, builder: Any, c: Any, st: dict[str, Any], width: int) -> None:
        for i in range(width):
            self._xm(builder, c, st["fv"][i], st["gv"][i])

    def _omega(self, builder: Any, gv: list[Any], s: Any) -> None:
        for i in range(self.t - 1, -1, -1):
            for k in range(1, i + 1):
                self._xm(builder, gv[k], s[i - k], s[i])

    def _omega_undo(self, builder: Any, gv: list[Any], s: Any) -> None:
        for i in range(self.t):
            for k in range(1, i + 1):
                self._xm(builder, gv[k], s[i - k], s[i])

    def _tower_ops(self, builder: Any, fast: bool = True) -> Any:
        return super()._tower_ops(builder, fast)

    def _chien_forney(self, builder: Any, gv: list[Any], gu: list[Any], error_mbuc: Any) -> None:
        """The Forney scan with the `sigma(beta)` accumulator released while the tower division runs.

        `sg` is a CNOT image of the coefficient registers, so it is cleared before the division and rebuilt
        for the zero-test uncompute at no Toffoli cost (the same trick as the Lanczos scan).
        """
        if not self._fast:
            super()._chien_forney(builder, gv, gu, error_mbuc)
            return
        t, gf, deg = self.t, self.gf, self.deg
        order = (1 << deg) - 1
        alpha = gf.primitive_element
        m = len(error_mbuc)
        steps = [(gv[k], gf.pow(alpha, (-k) % order)) for k in range(1, t + 1)]
        steps += [(gu[k], gf.pow(alpha, (-(k + 1)) % order)) for k in range(t)]
        steps = [(reg, c) for reg, c in steps if c != 1]
        od, om = (builder.alloc_qubits(deg) for _ in range(2))
        od_src = _cat([gv[k] for k in range(1, t + 1, 2)])
        od_dst = _cat([od for _ in range(1, t + 1, 2)])
        om_src = _cat([gu[k] for k in range(t)])
        om_dst = _cat([om for _ in range(t)])
        sg_src = _cat([gv[k] for k in range(1, t + 1)])
        position = builder.mark("forney_position")
        tower = self._tower_ops(builder)

        def fill_sg() -> Any:
            sg = builder.alloc_qubits(deg)
            builder.cx(sg_src, _cat([sg for _ in range(t)]))
            builder.x(sg[0])  # sigma_0 = 1 after normalisation (gv[0] holds the scale)
            return sg

        def clear_sg(sg: Any) -> None:
            builder.x(sg[0])
            builder.cx(sg_src, _cat([sg for _ in range(t)]))
            builder.free(sg)

        for j in range(m):
            with position:
                builder.cx(od_src, od_dst)
                builder.cx(om_src, om_dst)
                sg = fill_sg()
                ladder = self._zero_test(builder, sg)
                z = ladder[-1]
                builder.x(sg)  # undo the zero test's complement, then release sg during the division
                clear_sg(sg)
                tower(od, om, z, error_mbuc[j])
                sg = fill_sg()
                builder.x(sg)
                self._zero_untest(builder, sg, ladder)
                clear_sg(sg)
                builder.cx(od_src, od_dst)
                builder.cx(om_src, om_dst)
                if j + 1 < m:
                    for reg, c in steps:
                        builder.gf2_imul(c, target=reg, field=gf)
        if m > 1:
            for reg, c in steps:
                builder.gf2_idiv(gf.pow(c, m - 1), target=reg, field=gf)
        for reg in (od, om):
            builder.free(reg)

    # delta >= 0 (ties replace): stored value delta + OFFSET > OFFSET - 1
    def _sw_flags(self, builder: Any, delta: Any, d_reg: Any) -> tuple[Any, Any]:
        gt = builder.alloc_qubits(1)[0]
        nz = builder.alloc_qubits(1)[0]
        builder.flip_if_greater_than(delta, OFFSET - 1, target=gt)
        builder.flip_if_equal(d_reg, 0, target=nz)
        builder.x(nz)
        return gt, nz

    def _unflag(self, builder: Any, delta: Any, d_reg: Any, gt: Any, nz: Any) -> None:
        builder.x(nz)
        builder.flip_if_equal(d_reg, 0, target=nz)
        builder.flip_if_greater_than(delta, OFFSET - 1, target=gt)
        builder.free(nz)
        builder.free(gt)

    @staticmethod
    def _flag_nonzero(builder: Any, reg: Any, flag: Any) -> None:
        """flag ^= (reg != 0); `reg` is unchanged."""
        ladder = DivstepDecoder._zero_test(builder, reg)
        builder.cx(ladder[-1], flag)
        builder.x(flag)
        DivstepDecoder._zero_untest(builder, reg, ladder)

    def _xor_replace_quotient(self, builder: Any, fv0: Any, bb: Any, c: Any) -> None:
        """c ^= 1 / (f[0] * b): the quotient of a swap step from its after-state (zero when f[0] = 0)."""
        gf = self.gf
        if not self._fast:
            prod = builder.init_gf2_mul(fv0, bb, field=gf)
            inv = builder.init_gf2_inverse(prod, field=gf)
            builder.cx(inv, c)
            builder.del_gf2_inverse(prod, target=inv, field=gf)
            builder.free(inv)
            builder.del_gf2_mul(fv0, bb, target=prod, field=gf)
            builder.free(prod)
            return
        prod = builder.alloc_qubits(self.deg)
        self._xm(builder, fv0, bb, prod)
        inv = builder.alloc_qubits(self.deg)
        self._tinv(builder, prod, inv, clear=False)
        builder.cx(inv, c)
        self._tinv(builder, prod, inv, clear=True)
        builder.free(inv)
        builder.del_gf2_mul(fv0, bb, target=prod, field=gf)
        builder.free(prod)

    def _div_init(self, builder: Any, d_reg: Any, bb: Any) -> Any:
        """A fresh register holding `d / b`."""
        if not self._fast:
            return builder.init_gf2_div(d_reg, bb, field=self.gf)
        inv = builder.alloc_qubits(self.deg)
        self._tinv(builder, bb, inv, clear=False)
        c = builder.alloc_qubits(self.deg)
        self._xm(builder, d_reg, inv, c)
        self._tinv(builder, bb, inv, clear=True)
        builder.free(inv)
        return c

    def _div_del(self, builder: Any, d_reg: Any, bb: Any, c: Any) -> None:
        """Clears `c` known to hold `d / b`."""
        if not self._fast:
            builder.del_gf2_div(d_reg, bb, target=c, field=self.gf)
            return
        inv = builder.alloc_qubits(self.deg)
        self._tinv(builder, bb, inv, clear=False)
        builder.del_gf2_mul(d_reg, inv, target=c, field=self.gf)
        self._tinv(builder, bb, inv, clear=True)
        builder.free(inv)

    @staticmethod
    def _index_bits(si: Any, value: int) -> Any:
        return km.array([si[i] for i in range(len(si)) if value >> i & 1])

    def _forward_step(self, builder: Any, k: int, s: Any, st: dict[str, Any]) -> None:
        t, gf = self.t, self.gf
        gv, fv, bb, delta = st["gv"], st["fv"], st["b"], st["delta"]
        w = self._width(k)
        with builder.mark("discrepancy"):
            d_reg = builder.alloc_qubits(self.deg)
            for i in range(w):
                self._xm(builder, gv[i], s[k - i], d_reg)
        with builder.mark("swap_decision"):
            gt, nz = self._sw_flags(builder, delta, d_reg)
            sw = builder.alloc_qubits(1)[0]
            builder.init_and(gt, nz, sw)
            self._unflag(builder, delta, d_reg, gt, nz)
        with builder.mark("swap_rows"):
            builder.cswap(sw, d_reg, bb)
            builder.cswap(sw, _cat(gv[:w]), _cat(fv[:w]))
            self._negate_delta(builder, delta, sw)
            builder.iadd(1, target=delta)
        with builder.mark("quotient"):
            c = self._div_init(builder, d_reg, bb)
        with builder.mark("row_update"):
            self._update_rows(builder, c, st, w)
        builder.del_gf2_mul(c, bb, target=d_reg, field=gf)
        builder.free(d_reg)
        with builder.mark("dialog_free"):
            # swap step: c = 1 / (f[0] b) is recomputable, clear it; sw = (f[0] != 0) likewise
            self._xor_replace_quotient(builder, fv[0], bb, c)
            self._flag_nonzero(builder, fv[0], sw)
            builder.free(sw)
            # retain step: c moves onto the stack with its index
            rf = builder.alloc_qubits(1)[0]
            self._flag_nonzero(builder, c, rf)
            builder.cswap(rf, c, st["sv"])
            builder.cx(rf, self._index_bits(st["si"], k + 1))
            builder.flip_if_equal(st["si"], k + 1, target=rf)
            builder.free(rf)
            builder.free(c)
        sh = None
        if k < t:
            fv.insert(0, fv.pop())
        else:
            with builder.mark("shift_f"):
                sh = builder.alloc_qubits(1)[0]
                self._shift_flag(builder, fv[t], sh)
                self._shift_f(builder, fv, sh)
        st["sh"].append(sh)

    def _backward_step(self, builder: Any, k: int, s: Any, st: dict[str, Any]) -> None:
        t, gf = self.t, self.gf
        gv, fv, bb, delta = st["gv"], st["fv"], st["b"], st["delta"]
        sh = st["sh"].pop()
        w = self._width(k)
        if sh is None:
            fv.append(fv.pop(0))
        else:
            with builder.mark("shift_f"):
                self._shift_f(builder, fv, sh, inverse=True)
                self._shift_flag(builder, fv[t], sh)
                builder.free(sh)
        with builder.mark("dialog_free"):
            c = builder.alloc_qubits(self.deg)
            sw = builder.alloc_qubits(1)[0]
            self._flag_nonzero(builder, fv[0], sw)
            rf = builder.alloc_qubits(1)[0]
            builder.flip_if_equal(st["si"], k + 1, target=rf)
            builder.cswap(rf, c, st["sv"])
            builder.cx(rf, self._index_bits(st["si"], k + 1))
            self._flag_nonzero(builder, c, rf)
            builder.free(rf)
            self._xor_replace_quotient(builder, fv[0], bb, c)
        d_reg = builder.alloc_qubits(self.deg)
        builder.init_gf2_mul(c, bb, target=d_reg, field=gf)
        with builder.mark("row_update"):
            self._update_rows(builder, c, st, w)
        with builder.mark("quotient"):
            self._div_del(builder, d_reg, bb, c)
        builder.free(c)
        with builder.mark("swap_rows"):
            builder.isub(1, target=delta)
            self._negate_delta(builder, delta, sw)
            builder.cswap(sw, _cat(gv[:w]), _cat(fv[:w]))
            builder.cswap(sw, d_reg, bb)
        with builder.mark("swap_decision"):
            gt, nz = self._sw_flags(builder, delta, d_reg)
            builder.del_and(gt, nz, sw)
            self._unflag(builder, delta, d_reg, gt, nz)
            builder.free(sw)
        with builder.mark("discrepancy_clear"):
            mask = builder.alloc_bits(self.deg)
            builder.hmr(d_reg, mask)
            for i in range(w):
                builder.gf2_phase_by_product(gv[i], s[k - i], mask=mask, field=gf)
            builder.free(mask)
            builder.free(d_reg)

    def build_syndrome_decoding_mbuc(self, builder: Any, *, syndromes: Any, error_mbuc: Any) -> None:
        n, t = self.n, self.t
        if len(syndromes) != n:
            raise ValueError(f"Expected {n} syndrome registers, got {len(syndromes)}.")
        self._tw = None
        self._fm = None
        width = (n + 2 * OFFSET + 2).bit_length() + 1
        st: dict[str, Any] = {
            "gv": self._alloc_regs(builder, t + 1),
            "fv": self._alloc_regs(builder, t + 1),
            "b": builder.alloc_qubits(self.deg),
            "delta": builder.alloc_qubits(width),
            "sv": builder.alloc_qubits(self.deg),
            "si": builder.alloc_qubits((n + 1).bit_length()),
            "sh": [],
        }
        init_ones = km.array([st["gv"][0][0], st["b"][0]])
        builder.x(init_ones)
        builder.iadd(OFFSET + 1, target=st["delta"])
        with builder.mark("forward_divsteps"):
            for k in range(n):
                self._forward_step(builder, k, syndromes, st)
        with builder.mark("omega"):
            self._normalise(builder, st["gv"])
            self._omega(builder, st["gv"], syndromes)
        with builder.mark("chien_forney_mbuc"):
            self._chien_forney(builder, st["gv"], list(syndromes[:t]), error_mbuc)
        with builder.mark("omega_clear"):
            self._omega_undo(builder, st["gv"], syndromes)
            self._unnormalise(builder, st["gv"])
        with builder.mark("reverse_divsteps"):
            for k in range(n - 1, -1, -1):
                self._backward_step(builder, k, syndromes, st)
        builder.isub(OFFSET + 1, target=st["delta"])
        builder.x(init_ones)
        for reg in (*st["gv"], *st["fv"], st["b"], st["delta"], st["sv"], st["si"]):
            builder.free(reg)


def build_circuit(m: int, n: int, degree: int) -> Any:
    builder = km.CircuitBuilder()
    syndromes = [builder.create_quantum_register(degree, name=f"S{i}") for i in range(n)]
    error_mbuc = [builder.create_classical_register(degree, name=f"E{j}") for j in range(m)]
    BMDecoder(n, km.GF2Field(degree)).build_syndrome_decoding_mbuc(
        builder, syndromes=syndromes, error_mbuc=error_mbuc
    )
    return builder.finish_circuit()
