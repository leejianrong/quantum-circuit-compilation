# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# f16_merge.py: carry-erasure game with DEFERRED, MERGED fix-up blocks.
# Extends builds/t4/t4_pebble.py: erasing c_j while c_{j-1} is not live records a debt (b, j), b = highest live carry below j
# (0 = base, always live).  All pending debts with the same base b are repaid in one merged block (before c_b is erased, or
# at the end for b = 0): carries c_{b+1}.. are recomputed level by level, c_m under the OR of the debts that need it
# (debt j needs c_{b+1}..c_{j-1}); expected cost of c_m = 1 - 2^-k_m Toffolis (k_m debts need it); the block needs
# (max j - 1 - b) free ancillas.  A single debt costs (j-1-b)/2, as in the old game.  [modelled]
import heapq, sys, itertools

def block_cost(b, js):
    js = sorted(js); c = 0.0
    for m in range(b + 1, js[-1]):
        k = sum(1 for j in js if j > m); c += 1 - 0.5 ** k
    return c

def solve(n, w, start_t=0, start_L=(), top_slot=False):
    start = (start_t, frozenset(start_L), frozenset())
    dist = {start: 0.0}; prev = {start: None}; pq = [(0.0, 0, start)]; cnt = itertools.count(1)
    while pq:
        d, _, st = heapq.heappop(pq)
        if dist.get(st, 1e18) < d - 1e-12: continue
        t, L, D = st
        if t == n and not L and not D:
            path = []
            while prev[st] is not None: path.append(prev[st][1]); st = prev[st][0]
            return d, path[::-1]
        mv = []
        if t < n and (t == 0 or t in L):
            if t + 1 < n:
                if len(L) + 1 <= w: mv.append((0.0, (t + 1, L | {t + 1}, D), f'compute c{t+1}'))
            elif (not top_slot) or len(L) + 1 <= w: mv.append((0.0, (t + 1, L, D), f'compute c{n} in place'))
        bases = {b for b, j in D}
        for j in L:
            if j >= t or j in bases: continue
            if j == 1 or (j - 1) in L: mv.append((0.0, (t, L - {j}, D), f'erase c{j} free'))
            else:
                below = [i for i in L if i < j]; b = max(below) if below else 0
                mv.append((0.0, (t, L - {j}, D | {(b, j)}), f'erase c{j} defer base c{b}'))
        for b in bases:
            js = [j for bb, j in D if bb == b]
            if b != 0 and b not in L: continue
            if max(js) - 1 - b > w - len(L): continue
            if b == 0 and (L or t < n): continue          # base-0 debts are paid once, at the very end
            mv.append((block_cost(b, js), (t, L, frozenset(x for x in D if x[0] != b)), f'pay base c{b} debts {sorted(js)}'))
        for c, s2, lab in mv:
            s2 = (s2[0], frozenset(s2[1]), frozenset(s2[2])); nd = d + c
            if nd < dist.get(s2, 1e18) - 1e-12:
                dist[s2] = nd; prev[s2] = (st, lab); heapq.heappush(pq, (nd, next(cnt), s2))
    return None, None

if __name__ == '__main__':
    for n, w, st, sl, ts in [(12, 5, 0, (), False), (13, 5, 0, (), False), (10, 5, 0, (), False), (9, 5, 0, (), False),
                             (12, 4, 1, (1,), False), (12, 4, 1, (1,), True)]:
        d, p = solve(n, w, st, sl, ts)
        print(f'n={n} w={w} start={st},{sl} top_slot={ts}: merged-debt optimum {d:.4f} expected Toffolis', flush=True)
        for x in p: print('     ', x)
