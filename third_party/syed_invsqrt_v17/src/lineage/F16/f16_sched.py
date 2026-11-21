# Copyright 2026 Syed Asad Ali. Licensed under Apache-2.0.
# f16_sched.py: optimal carry-erasure schedules (builds/t4 erasure game) with path reconstruction.
import heapq, sys
def solve(n, w):
    start = (0, frozenset()); dist = {start: 0}; prev = {start: None}
    pq = [(0, 0, start)]; cnt = 1
    while pq:
        d, _, st = heapq.heappop(pq); t, L = st
        if dist.get(st, 1 << 30) < d: continue
        if t == n and not L:
            path = []
            while st is not None:
                p = prev[st]; 
                if p is None: break
                path.append(p[1]); st = p[0]
            return d, path[::-1]
        moves = []
        if t < n and (t == 0 or t in L):
            if t + 1 < n:
                if len(L) + 1 <= w: moves.append((0, (t + 1, L | {t + 1}), f'compute c{t+1}'))
            else: moves.append((0, (t + 1, L), f'compute c{n} in place'))
        for j in range(1, min(t, n - 1) + 1):
            if j not in L and (j == 1 or (j - 1) in L) and len(L) + 1 <= w:
                moves.append((2, (t, L | {j}), f'RECOMPUTE c{j}'))
        for j in L:
            if j >= t: continue
            if j == 1 or (j - 1) in L: moves.append((0, (t, L - {j}), f'erase c{j} free'))
            else:
                below = [i for i in L if i < j]; i = max(below) if below else 0
                g = j - 1 - i
                if g <= w - (len(L) - 1): moves.append((g, (t, L - {j}), f'erase c{j} cond gap {g} (c{i+1}..c{j-1} from c{i})'))
        for c, st2, lab in moves:
            st2 = (st2[0], frozenset(st2[1])); nd = d + c
            if nd < dist.get(st2, 1 << 30):
                dist[st2] = nd; prev[st2] = ((t, L), lab); heapq.heappush(pq, (nd, cnt, st2)); cnt += 1
if __name__ == '__main__':
  for n in (12, 13):
    d, path = solve(n, 5)
    print(f'n={n} w=5 extra expected Toffolis {d/2}')
    for p in path: print('   ', p)

def solve2(n, w, start_t=0, start_L=(), top_slot=False):
    """Same game; optional start state (carries already live) and 'top_slot': the in-place top needs one free ancilla
    (the last step's b360 phase CZ(c_top, q7) wants c_top on a wire). Returns (units, path); 1 unit = 0.5 Toffoli."""
    start = (start_t, frozenset(start_L)); dist = {start: 0}; prev = {start: None}
    pq = [(0, 0, start)]; cnt = 1
    while pq:
        d, _, st = heapq.heappop(pq); t, L = st
        if dist.get(st, 1 << 30) < d: continue
        if t == n and not L:
            path = []
            while prev[st] is not None:
                path.append(prev[st][1]); st = prev[st][0]
            return d, path[::-1]
        moves = []
        if t < n and (t == 0 or t in L):
            if t + 1 < n:
                if len(L) + 1 <= w: moves.append((0, (t + 1, L | {t + 1}), f'compute c{t+1}'))
            elif (not top_slot) or len(L) + 1 <= w: moves.append((0, (t + 1, L), f'compute c{n} in place'))
        for j in L:
            if j >= t: continue
            if j == 1 or (j - 1) in L: moves.append((0, (t, L - {j}), f'erase c{j} free'))
            else:
                below = [i for i in L if i < j]; i = max(below) if below else 0
                g = j - 1 - i
                if g <= w - (len(L) - 1): moves.append((g, (t, L - {j}), f'erase c{j} cond gap {g} (c{i+1}..c{j-1} from c{i})'))
        for c, st2, lab in moves:
            st2 = (st2[0], frozenset(st2[1])); nd = d + c
            if nd < dist.get(st2, 1 << 30):
                dist[st2] = nd; prev[st2] = ((t, L), lab); heapq.heappush(pq, (nd, cnt, st2)); cnt += 1
    return None, None

def _moves(n, w, t, L, top_slot):
    mv = []
    if t < n and (t == 0 or t in L):
        if t + 1 < n:
            if len(L) + 1 <= w: mv.append((0, (t + 1, L | {t + 1}), f'compute c{t+1}'))
        elif (not top_slot) or len(L) + 1 <= w: mv.append((0, (t + 1, L), f'compute c{n} in place'))
    for j in L:
        if j >= t: continue
        if j == 1 or (j - 1) in L: mv.append((0, (t, L - {j}), f'erase c{j} free'))
        else:
            below = [i for i in L if i < j]; i = max(below) if below else 0
            g = j - 1 - i
            if g <= w - (len(L) - 1): mv.append((g, (t, L - {j}), f'erase c{j} cond gap {g} (c{i+1}..c{j-1} from c{i})'))
    return [(c, (s[0], frozenset(s[1])), lab) for c, s, lab in mv]

def solve_branch(n, w, start_t, start_L, ccz_units=2):
    """Shared prefix, then a split on a random flag (p = 1/2): branch A needs a free slot at the top (else pays ccz_units),
    branch B is unconstrained.  Units: 1 = one CCX at p = 1/2 of the whole step.  Returns (best, split_state, prefix, pathA, pathB)."""
    start = (start_t, frozenset(start_L))
    # all reachable states
    seen = {start}; stack = [start]
    while stack:
        t, L = stack.pop()
        for _, s2, _ in _moves(n, w, t, L, False):
            if s2 not in seen: seen.add(s2); stack.append(s2)
    goal = lambda s: s[0] == n and not s[1]
    def values(top_slot):
        INF = 1 << 30; V = {s: (0 if goal(s) else INF) for s in seen}; arg = {}
        for _ in range(200):
            ch = False
            for s in seen:
                if goal(s): continue
                for c, s2, lab in _moves(n, w, s[0], s[1], top_slot):
                    if s2 in V and c + V[s2] < V[s]: V[s] = c + V[s2]; arg[s] = (s2, lab); ch = True
            if not ch: break
        return V, arg
    Vs, As = values(True); Vf, Af = values(False)
    def path(s, arg):
        p = []
        while not goal(s): s, lab = arg[s]; p.append(lab)
        return p
    # prefix distances (shared part, unconstrained moves, before the top)
    import heapq as hq
    dist = {start: 0}; prev = {start: None}; pq = [(0, 0, start)]; cnt = 1
    while pq:
        d, _, s = hq.heappop(pq)
        if dist[s] < d: continue
        for c, s2, lab in _moves(n, w, s[0], s[1], False):
            if s2[0] == n: continue
            if d + c < dist.get(s2, 1 << 30): dist[s2] = d + c; prev[s2] = (s, lab); hq.heappush(pq, (d + c, cnt, s2)); cnt += 1
    best = None
    for s, d in dist.items():
        va = min(Vs[s], Vf[s] + ccz_units); vb = Vf[s]
        tot = 2 * d + va + vb            # in half-units (x 0.5 of a unit)
        if best is None or tot < best[0]: best = (tot, s, va == Vs[s])
    tot, s, slot = best
    pre = []; x = s
    while prev[x] is not None: pre.append(prev[x][1]); x = prev[x][0]
    pre = pre[::-1]
    pa = path(s, As) if slot else path(s, Af)
    return tot / 2, s, pre, pa, path(s, Af), slot
