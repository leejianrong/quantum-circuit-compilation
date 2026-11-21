#!/usr/bin/env python3
# Copyright 2026 Syed Asad Ali. SPDX-License-Identifier: Apache-2.0.
# Credits: Opus and Astra.
"""Re-fit the generic rotation angles of the ring26 phase endpoint by a max-margin LP.

The circuit's phase is  sum_i feature_i(x) * angle_i  + fixed T/S/Z features  (mod 1 turn), where the
features come from the pinned integer arithmetic model (routed ring bits r, exponent k). The frozen
"global_zero33" angles were found by a cutting-plane LP with deltas BOUNDED to +-4 units of 2^-37
turn, four of them ended on the bound, and its record says LP_global_optimum_claim = false.

This tool solves the same LP without that trust region (cutting planes over all 3,133,452 official
inputs, HiGHS), quantises the result to the 2^-50-turn grid, and then screens EVERY input exactly
with integers against the official verifier's reference values and tolerance. It reports the exact
minimum margin (units of 2^-64 turn) and the rotation charge the official cost formula would give.

Nothing here changes a circuit. Output: a JSON angle table for tools/apply_angles.py.
Usage: macrun.py tools/refit_angles.py --out runs/refit/angles.json [--free-global] [--fix-zero SITE ...]
"""
from pathlib import Path
import argparse, hashlib, json, math, sys, time
import numpy as np

HERE = Path(__file__).resolve().parent
FG = HERE.parent
CAND10 = FG / 'work/c10/narrow/arithmetic_round2/native/candidate10'
sys.path.insert(0, str(CAND10))
sys.path.insert(0, str(HERE))
MAX_X = 3133452
N_SITES = 34


def load_everything():
    import arithmetic_variant as variant
    import prove_any
    proof = prove_any.original_proof(variant)
    oracle = sys.modules['candidate07_explicit_local_ring26_oracle50']
    return variant, proof, oracle


def features(oracle, xs):
    """(F, fixed_units50, k) from the pinned arithmetic model, exactly as oracle50.phase_units50."""
    old, chart = oracle._model.phase_units(xs, return_chart=True)
    old = np.asarray(old, dtype=np.int64); k = np.asarray(chart['flags'], dtype=np.int64)
    z = old & ((1 << 27) - 1); P = ((z >> k) | (z << (27 - k))) & ((1 << 27) - 1)
    W = P >> 1; r = ((W << k) | (W >> (26 - k))) & ((1 << 26) - 1)
    F = np.zeros((len(xs), N_SITES), dtype=np.int8)
    for i in range(26):
        F[:, i] = (r >> i) & 1
    for j in range(7):
        F[:, 26 + j] = ((r >> j) & 1) * (k > j)
    F[:, 33] = 1
    fixed = np.zeros(len(xs), dtype=np.int64)
    for j in (7, 8, 9):
        fixed += ((r >> j) & 1) * (k > j) * (1 << (40 + j))
    return F, fixed, k


def reference(xs):
    """Official verifier's target and tolerance (uint64, units of 2^-64 turn), beta = 1, 24 bits."""
    target, tol = [], []
    num = 1 << 130
    for x in xs.tolist():
        r = math.isqrt(num // x)
        target.append(((r + 1) >> 1) & ((1 << 64) - 1)); tol.append(min(r >> 25, 1 << 63))
    return np.array(target, dtype=np.uint64), np.array(tol, dtype=np.uint64)


def exact_screen(F, fixed, target, tol, angles):
    """Exact integer margins for an angle table (units of 2^-50 turn)."""
    phase = fixed.copy()
    for i in range(N_SITES):
        if angles[i]:
            phase += F[:, i].astype(np.int64) * np.int64(angles[i] % (1 << 50))
    phase &= (1 << 50) - 1
    theta = phase.astype(np.uint64) << np.uint64(14)
    error = (theta - target).view(np.int64)
    used = np.abs(error).view(np.uint64)
    margin = tol.astype(np.int64) - used.astype(np.int64)
    ratio = used / tol
    worst = int(np.argmax(ratio))
    return dict(failures=int((margin < 0).sum()), minimum_margin_units64=int(margin.min()),
                minimum_margin_x=int(np.argmin(margin)) + 1, worst_error_over_tolerance=float(ratio[worst]),
                worst_x=worst + 1), error, phase


def rotation_charge(margin_units64, n_rot):
    eps = math.pi * margin_units64 / 2**64 / n_rot
    return n_rot * (0.56 * math.log2(1 / eps) + 5.3) / 4, eps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--free-global', action='store_true', help='let the global-one site rotate (34 rotations)')
    ap.add_argument('--fix-zero', nargs='*', default=[], help='site indices forced to angle 0 (fewer rotations)')
    ap.add_argument('--bound-units37', type=float, default=None, help='optional symmetric delta bound')
    ap.add_argument('--rounds', type=int, default=40)
    args = ap.parse_args()
    began = time.monotonic()
    from scipy.optimize import linprog
    variant, proof, oracle = load_everything()
    old_angles = [int(a) for a in oracle.ANGLES]
    xs = np.arange(1, MAX_X + 1, dtype=np.uint64)
    F, fixed, k = features(oracle, xs)
    assert np.array_equal(exact_screen(F, fixed, *reference(xs[:1000]), old_angles)[2][:1000] if False else
                          oracle.phase_units50(xs[:4096]).astype(np.int64),
                          ((fixed[:4096] + (F[:4096].astype(np.int64) * np.array(old_angles, dtype=np.int64)).sum(axis=1))
                           & ((1 << 50) - 1)))
    target, tol = reference(xs)
    base, base_error, _ = exact_screen(F, fixed, target, tol, old_angles)
    print('frozen angles:', json.dumps(base), 'rotation charge %.6f' % rotation_charge(base['minimum_margin_units64'], 33)[0], flush=True)
    fixed_zero = set(int(s) for s in args.fix_zero)
    if not args.free_global:
        fixed_zero.add(33)
    free = [i for i in range(N_SITES) if i not in fixed_zero]
    # LP in units of 2^-37 turn (2^27 units64). Unknown: delta for free sites, and for a site forced to zero the
    # delta is -old angle (a constant shift folded into the base error).
    UNIT = float(1 << 27)
    shift = np.zeros(MAX_X)
    for i in fixed_zero:
        if old_angles[i]:
            shift -= F[:, i].astype(np.float64) * (old_angles[i] * (1 << 14) / UNIT)
    e0 = base_error.astype(np.float64) / UNIT + shift
    tl = tol.astype(np.float64) / UNIT
    Ff = F[:, free].astype(np.float32)
    slack0 = tl - np.abs(e0)
    active = set(np.argsort(slack0)[:4000].tolist())
    delta = np.zeros(len(free)); t = None
    for rnd in range(args.rounds):
        idx = np.array(sorted(active))
        A = Ff[idx].astype(np.float64)
        ones = np.ones((len(idx), 1))
        A_ub = np.vstack([np.hstack([A, ones]), np.hstack([-A, ones])])
        b_ub = np.concatenate([tl[idx] - e0[idx], tl[idx] + e0[idx]])
        c = np.zeros(len(free) + 1); c[-1] = -1.0
        bound = (None, None) if args.bound_units37 is None else (-args.bound_units37, args.bound_units37)
        res = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=[bound] * len(free) + [(None, None)], method='highs')
        assert res.status == 0, res.message
        delta, t = res.x[:-1], res.x[-1]
        err = e0 + Ff @ delta.astype(np.float32).astype(np.float64) if False else e0 + (Ff.astype(np.float64) @ delta)
        slack = tl - np.abs(err)
        full = float(slack.min())
        print(f'round {rnd}: active {len(idx)}  LP margin {t:.6f}  full margin {full:.6f} units37', flush=True)
        if full >= t - 1e-7:
            break
        worst = np.argsort(slack)[:3000].tolist()
        active.update(worst)
    # Quantise to the 2^-50 grid and screen exactly.
    new_angles = list(old_angles)
    for i in fixed_zero:
        new_angles[i] = 0
    for n, i in enumerate(free):
        new_angles[i] = old_angles[i] + int(round(delta[n] * UNIT / (1 << 14)))
    screen, _, phase = exact_screen(F, fixed, target, tol, new_angles)
    n_rot = sum(1 for i in range(N_SITES) if new_angles[i] % (1 << 47))   # not a multiple of 1/8 turn
    n_t = sum(1 for i in range(N_SITES) if new_angles[i] % (1 << 47) == 0 and new_angles[i] % (1 << 48))
    result = dict(status='EXACT_ALL_INPUT_SCREEN_OF_REFIT_ANGLES_NOT_A_CIRCUIT',
                  sites=list(oracle.SITES), old_angles_units50=old_angles, new_angles_units50=new_angles,
                  delta_units50=[n - o for n, o in zip(new_angles, old_angles)],
                  lp_margin_units37=float(t), frozen=base, refit=screen,
                  generic_rotations=n_rot, t_like_sites=n_t,
                  frozen_rotation_charge=rotation_charge(base['minimum_margin_units64'], 33)[0],
                  refit_rotation_charge=rotation_charge(screen['minimum_margin_units64'], n_rot)[0] if screen['minimum_margin_units64'] > 0 else None,
                  phase50_sha256=hashlib.sha256((phase.astype(np.uint64)).astype('<u8').tobytes()).hexdigest(),
                  free_global=bool(args.free_global), fixed_zero=sorted(fixed_zero), seconds=time.monotonic() - began)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=1) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('old_angles_units50', 'new_angles_units50', 'delta_units50', 'sites')}, indent=1))
    print('delta units37:', [round(d / (1 << 13), 3) for d in result['delta_units50']])


if __name__ == '__main__':
    main()
