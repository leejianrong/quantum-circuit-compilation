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


class BMDecoder(DivstepDecoder):
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
        prod = builder.init_gf2_mul(fv0, bb, field=gf)
        inv = builder.init_gf2_inverse(prod, field=gf)
        builder.cx(inv, c)
        builder.del_gf2_inverse(prod, target=inv, field=gf)
        builder.free(inv)
        builder.del_gf2_mul(fv0, bb, target=prod, field=gf)
        builder.free(prod)

    @staticmethod
    def _index_bits(si: Any, value: int) -> Any:
        return km.array([si[i] for i in range(len(si)) if value >> i & 1])

    def _forward_step(self, builder: Any, k: int, s: Any, st: dict[str, Any]) -> None:
        t, gf = self.t, self.gf
        gv, fv, bb, delta = st["gv"], st["fv"], st["b"], st["delta"]
        w = min(t, k) + 1
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
            builder.cswap(sw, _cat(gv[:w]), _cat(fv[:w]))
            self._negate_delta(builder, delta, sw)
            builder.iadd(1, target=delta)
        with builder.mark("quotient"):
            c = builder.init_gf2_div(d_reg, bb, field=gf)
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
        w = min(t, k) + 1
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
            builder.del_gf2_div(d_reg, bb, target=c, field=gf)
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
            for i in range(min(t, k) + 1):
                builder.gf2_phase_by_product(gv[i], s[k - i], mask=mask, field=gf)
            builder.free(mask)
            builder.free(d_reg)

    def build_syndrome_decoding_mbuc(self, builder: Any, *, syndromes: Any, error_mbuc: Any) -> None:
        n, t = self.n, self.t
        if len(syndromes) != n:
            raise ValueError(f"Expected {n} syndrome registers, got {len(syndromes)}.")
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
