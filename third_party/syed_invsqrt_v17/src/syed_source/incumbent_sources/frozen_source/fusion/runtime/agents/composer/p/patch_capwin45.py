# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""COMPOSER copy of agents/tk_q46/p/patch_capwin46.py for a Q45 STUDY, MEASUREMENT ONLY: cap CMP_CAP_BASE (default 45)
from the normalization entry on, raised to BASE+1 (46) only inside the blocks named in CMP_CAPWIN_BLOCKS (comma list).
List this patch LAST; build with --Q 46. Original header: Agent width, MEASUREMENT ONLY (Q46 study). Blocks: loader1 loader2 coef1 coef2 prodfwd seedfwd divfwd endpoint divider invprod seedclean coefinv
unpack tail norminv rootinv h3i h4.
"""
import functools, os, sys, types

BASE = int(os.environ.get('CMP_CAP_BASE', '45'))
WINDOW = BASE + 1
BLOCKS = [b for b in os.environ.get('CMP_CAPWIN_BLOCKS', '').split(',') if b]
LOG = []


def _with_cap(fn, label):
    @functools.wraps(fn)
    def wrapped(builder, *args, **kwargs):
        old = builder.max_qubits
        if label in BLOCKS:
            builder.set_max_qubits(WINDOW)
        try:
            return fn(builder, *args, **kwargs)
        except Exception:
            LOG.append(('FAILED_IN', label, builder.num_allocated_qubits))
            print('CMP_CAPWIN45 failure inside block', label, 'allocated', builder.num_allocated_qubits, file=sys.stderr)
            raise
        finally:
            builder.set_max_qubits(old)
    return wrapped


def apply(ctx):
    norm_mod = ctx.components['normalization']
    new_norm = types.SimpleNamespace(**{k: getattr(norm_mod, k) for k in dir(norm_mod) if not k.startswith('__')})
    fwd, inv = norm_mod.forward, norm_mod.inverse

    def forward(builder, original, flags):
        builder.set_max_qubits(BASE)
        return fwd(builder, original, flags)

    def inverse(builder, norm, flags):
        out = _with_cap(inv, 'norminv')(builder, norm, flags)
        builder.set_max_qubits(WINDOW)
        return out
    new_norm.forward, new_norm.inverse = forward, inverse
    ctx.components['normalization'] = new_norm
    root = ctx.components['root']
    new_root = types.SimpleNamespace(**{k: getattr(root, k) for k in dir(root) if not k.startswith('__')})
    new_root.inverse = _with_cap(root.inverse, 'rootinv')
    ctx.components['root'] = new_root
    d = ctx.old.divider
    d.cleanup_divider = _with_cap(d.cleanup_divider, 'divider')
    d.phase_endpoint = _with_cap(d.phase_endpoint, 'endpoint')
    d.compute_divider = _with_cap(d.compute_divider, 'divfwd')
    lc = ctx.components['lifecycle']
    lc.product_inverse = _with_cap(lc.product_inverse, 'invprod')
    bl = ctx.baseline
    bl.seed_cleanup = _with_cap(bl.seed_cleanup, 'seedclean')
    bl.seed_forward = _with_cap(bl.seed_forward, 'seedfwd')
    bl.product_forward = _with_cap(bl.product_forward, 'prodfwd')
    bl.coefficient_inverse = _with_cap(bl.coefficient_inverse, 'coefinv')
    bl.prepare_H3_initial = _with_cap(bl.prepare_H3_initial, 'h3i')
    bl.prepare_H4 = _with_cap(bl.prepare_H4, 'h4')
    cf = bl.coefficient_forward
    calls = {'n': 0}

    def coefficient_forward(builder, *a, **k):
        calls['n'] += 1
        return _with_cap(cf, 'coef1' if calls['n'] == 1 else 'coef2')(builder, *a, **k)
    bl.coefficient_forward = coefficient_forward
    t = ctx.tables
    load = t.load_joint16

    def load_joint16(builder, address7, *, variant, debts):
        return _with_cap(load, 'loader1' if variant == 'first' else 'loader2')(builder, address7, variant=variant, debts=debts)
    t.load_joint16 = load_joint16
    hret = [m for n, m in sys.modules.items() if n.startswith('variant_patch_patch_hret14_q4')]
    if hret:
        top = hret[0]._relaxed_top12()
        lfi = top.last_feed_and_initial

        def last_feed_and_initial(d, b, *a, **k):
            return _with_cap(lambda bb, *aa, **kk: lfi(d, bb, *aa, **kk), 'divfinal')(b, *a, **k)
        top.last_feed_and_initial = last_feed_and_initial
    body = [m for n, m in sys.modules.items() if n.startswith('variant_patch_patch_w47_body')]
    if body:
        b = body[0]
        if hasattr(b, 'unpack_h0_after_seed'):
            b.unpack_h0_after_seed = _with_cap(b.unpack_h0_after_seed, 'unpack')
        tm = b._tail_modules()
        tm['replay'] = _with_cap(tm['replay'], 'tail')
        paid = tm['paidR']
        paid.cleanup_joint18 = _with_cap(paid.cleanup_joint18, 'tail')
