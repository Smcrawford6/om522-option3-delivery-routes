"""Method 2, the researched method.

Three stages, each from the reading named in the brief:

1. Construction: Solomon's (1987) I1 time-window insertion heuristic, run from
   a small grid of its parameters (alpha1, lambda, seed rule; mu = 1); every
   start is improved by step 2 and the best one is kept.
2. Improvement: local search with the moves the brief lists, i.e., relocate
   (one to three consecutive customers, also known as or-opt), exchange of
   two customers between routes, reversal of a route segment (2-opt), and
   exchange of route tails (2-opt*, Potvin and Rousseau 1995).  Moves are
   limited to each customer's nearest neighbors (granular search, Toth and
   Vigo 2003) and are accepted on first improvement.
3. Ruin and recreate (large neighborhood search, Shaw 1998; Ropke and
   Pisinger 2006): remove a group of customers, reinsert them by regret-2
   insertion, run step 2 again, and accept the result by simulated annealing.
   Several independent chains start from the best step-2 solution, and the
   best result over all chains is returned.

Feasibility (capacity, windows, shift end, and the team's rule that a route
never crosses itself) is checked after every move, so the current solution
is always feasible.  The search stops after a fixed number of ruin and
recreate iterations per chain; the time limit is only a safety cap.  Chain c
draws from random.Random(100 * seed + c), so a rerun reproduces the result.
"""

import heapq
import math
import random
import time

from .core import EPS, route_cost, route_crosses, schedule

DEFAULT_ITERATIONS = 2000  # ruin-and-recreate iterations per chain
DEFAULT_CHAINS = 4
DEFAULT_SEED = 522
DEFAULT_TIME_LIMIT = 480.0  # seconds; the instructor allows 10 minutes in total
NEIGHBORS = 12
START_WORSE = 0.005  # a result this much worse is accepted half the time at the start

# Solomon I1 parameter grid: (alpha1, lambda, seed rule), with mu = 1.
I1_GRID = [
    (alpha1, lam, seed_rule)
    for seed_rule in ("farthest", "earliest_deadline")
    for lam in (1.0, 2.0)
    for alpha1 in (0.0, 0.5, 1.0)
]


class RouteSearch:
    """Holds one solution (a route per vehicle) and the moves that change it."""

    def __init__(self, inst):
        self.inst = inst
        self.routes = [[] for _ in range(inst.m)]
        self.load = [0] * inst.m
        self.cost = [0.0] * inst.m
        self.starts = [[] for _ in range(inst.m)]
        self.latest = [[] for _ in range(inst.m)]
        self.route_of = [-1] * (inst.n + 1)
        self.pos_of = [-1] * (inst.n + 1)
        self.touched = set()  # routes changed since the last reset
        _t = inst.t
        self.near = [[]] + [
            sorted((v for v in range(1, inst.n + 1) if v != u), key=lambda v: (_t[u][v], v))[:NEIGHBORS]
            for u in range(1, inst.n + 1)
        ]

    # --- bookkeeping -----------------------------------------------------

    def refresh(self, k):
        """Recompute the cached load, cost, times, and positions of route k."""
        inst, _r = self.inst, self.routes[k]
        self.touched.add(k)
        self.load[k] = sum(inst.demand[c] for c in _r)
        self.cost[k] = route_cost(_r, inst.t) if _r else 0.0
        for _p, _c in enumerate(_r):
            self.route_of[_c], self.pos_of[_c] = k, _p
        _sched = schedule(_r, k, inst) if _r else ([], [], inst.shift_start[k])
        self.starts[k] = _sched[1]
        # latest[p]: latest service start at position p that keeps the rest
        # of the route feasible (used for O(1) insertion checks).
        _latest = [0.0] * len(_r)
        _limit = inst.shift_end[k]
        _next = 0
        for _p in range(len(_r) - 1, -1, -1):
            _c = _r[_p]
            _limit = min(inst.late[_c], _limit - inst.t[_c][_next] - inst.service[_c])
            _latest[_p] = _limit
            _next = _c
        self.latest[k] = _latest

    def set_routes(self, routes):
        self.routes = [r[:] for r in routes]
        for _k in range(self.inst.m):
            self.refresh(_k)

    def total(self):
        return sum(self.cost)

    def feasible(self, route, k):
        if not route:
            return True
        if sum(self.inst.demand[c] for c in route) > self.inst.capacity[k]:
            return False
        return schedule(route, k, self.inst) is not None and not route_crosses(route, self.inst.xy)

    # --- insertion (construction and recreate) ---------------------------

    def insertion_options(self, u, k):
        """Feasible insertion positions of u in route k as (added travel, push, q).

        Time windows are checked in O(1) per position with the cached service
        starts and latest starts; crossings are checked later, lazily.
        """
        inst, _r = self.inst, self.routes[k]
        if self.load[k] + inst.demand[u] > inst.capacity[k]:
            return []
        _t, _service = inst.t, inst.service
        _starts, _latest = self.starts[k], self.latest[k]
        _options = []
        for _q in range(len(_r) + 1):
            _a = _r[_q - 1] if _q > 0 else 0
            _b = _r[_q] if _q < len(_r) else 0
            _depart = _starts[_q - 1] + _service[_a] if _q > 0 else inst.shift_start[k]
            _arrive = _depart + _t[_a][u]
            _start = _arrive if _arrive > inst.early[u] else inst.early[u]
            if _start > inst.late[u] + EPS:
                continue
            _arrive_b = _start + _service[u] + _t[u][_b]
            if _b == 0:
                _old = (_starts[-1] + _service[_r[-1]] + _t[_r[-1]][0]) if _r else inst.shift_start[k]
                if _arrive_b > inst.shift_end[k] + EPS:
                    continue
                _push = _arrive_b - _old
            else:
                _new_b = _arrive_b if _arrive_b > inst.early[_b] else inst.early[_b]
                if _new_b > _latest[_q] + EPS:
                    continue
                _push = _new_b - _starts[_q]
            _options.append((_t[_a][u] + _t[u][_b] - _t[_a][_b], _push, _q))
        return _options

    def crossing_free_insert(self, u, k, q):
        _r = self.routes[k]
        return not route_crosses(_r[:q] + [u] + _r[q:], self.inst.xy)

    def insert(self, u, k, q):
        self.routes[k].insert(q, u)
        self.refresh(k)

    # --- local search ------------------------------------------------------

    def _apply(self, k1, r1, k2=None, r2=None):
        """Accept new routes if they are feasible; return True when applied."""
        inst = self.inst
        for _r, _k in ((r1, k1), (r2, k2)) if k2 is not None else ((r1, k1),):
            if _r and (sum(inst.demand[c] for c in _r) > inst.capacity[_k] or schedule(_r, _k, inst) is None):
                return False
        if route_crosses(r1, inst.xy) or (k2 is not None and route_crosses(r2, inst.xy)):
            return False
        self.routes[k1] = r1
        self.refresh(k1)
        if k2 is not None:
            self.routes[k2] = r2
            self.refresh(k2)
        return True

    def _inter_moves(self, u, v):
        """Try relocate, exchange, and 2-opt* between the routes of u and v."""
        inst, _t = self.inst, self.inst.t
        ka, kb = self.route_of[u], self.route_of[v]
        A, B = self.routes[ka], self.routes[kb]
        pu, pv = self.pos_of[u], self.pos_of[v]

        # Relocate (or-opt): move A[pu:pu+L] next to v, either orientation.
        _pa = A[pu - 1] if pu > 0 else 0
        _seg_load, _inside, _inside_rev = 0, 0.0, 0.0
        for _L in (1, 2, 3):
            if pu + _L > len(A):
                break
            _seg = A[pu:pu + _L]
            _seg_load += inst.demand[_seg[-1]]
            if _L > 1:
                _inside += _t[_seg[-2]][_seg[-1]]
                _inside_rev += _t[_seg[-1]][_seg[-2]]
            if self.load[kb] + _seg_load > inst.capacity[kb]:
                break  # longer segments are heavier still
            _na = A[pu + _L] if pu + _L < len(A) else 0
            _removed = _t[_pa][_na] - _t[_pa][_seg[0]] - _t[_seg[-1]][_na]
            for _s, _diff in ((_seg, 0.0), (_seg[::-1], _inside_rev - _inside)) if _L > 1 else ((_seg, 0.0),):
                for _q in (pv, pv + 1):  # before v, after v
                    _x = B[_q - 1] if _q > 0 else 0
                    _y = B[_q] if _q < len(B) else 0
                    _delta = _removed + _diff + _t[_x][_s[0]] + _t[_s[-1]][_y] - _t[_x][_y]
                    if _delta < -EPS and self._apply(ka, A[:pu] + A[pu + _L:], kb, B[:_q] + _s + B[_q:]):
                        return True

        # Exchange u and v.
        _dl = inst.demand[v] - inst.demand[u]
        if self.load[ka] + _dl <= inst.capacity[ka] and self.load[kb] - _dl <= inst.capacity[kb]:
            _pa, _na = (A[pu - 1] if pu > 0 else 0), (A[pu + 1] if pu + 1 < len(A) else 0)
            _pb, _nb = (B[pv - 1] if pv > 0 else 0), (B[pv + 1] if pv + 1 < len(B) else 0)
            _delta = (_t[_pa][v] + _t[v][_na] - _t[_pa][u] - _t[u][_na]
                      + _t[_pb][u] + _t[u][_nb] - _t[_pb][v] - _t[v][_nb])
            if _delta < -EPS:
                _r1, _r2 = A[:], B[:]
                _r1[pu], _r2[pv] = v, u
                if self._apply(ka, _r1, kb, _r2):
                    return True

        # 2-opt*: A keeps its head through u and takes B's tail from v.
        _q = pv - 1
        _next_a = A[pu + 1] if pu + 1 < len(A) else 0
        _bq = B[_q] if _q >= 0 else 0
        _delta = _t[u][v] + _t[_bq][_next_a] - _t[u][_next_a] - _t[_bq][v]
        if _delta < -EPS:
            _r1, _r2 = A[:pu + 1] + B[_q + 1:], B[:_q + 1] + A[pu + 1:]
            if self._apply(ka, _r1, kb, _r2):
                return True
        return False

    def _intra_moves(self, k):
        """Exhaustive 2-opt and or-opt within route k (routes are short)."""
        _r, _t = self.routes[k], self.inst.t
        _base = self.cost[k]
        _len = len(_r)
        for _i in range(_len - 1):  # 2-opt: reverse _r[_i.._j]
            for _j in range(_i + 1, _len):
                _new = _r[:_i] + _r[_i:_j + 1][::-1] + _r[_j + 1:]
                if route_cost(_new, _t) < _base - EPS and self._apply(k, _new):
                    return True
        for _L in (1, 2, 3):  # or-opt: move _r[_i:_i+_L] elsewhere in the route
            for _i in range(_len - _L + 1):
                _seg, _rest = _r[_i:_i + _L], _r[:_i] + _r[_i + _L:]
                for _q in range(len(_rest) + 1):
                    if _q == _i:
                        continue
                    _new = _rest[:_q] + _seg + _rest[_q:]
                    if route_cost(_new, _t) < _base - EPS and self._apply(k, _new):
                        return True
        return False

    def local_search(self, dirty=None):
        """First-improvement descent until no move improves total travel.

        Only moves that touch a changed ("dirty") route are examined; a move
        between two unchanged routes was already non-improving.  dirty=None
        examines every route.
        """
        _dirty = set(k for k in range(self.inst.m) if self.routes[k]) if dirty is None else set(dirty)
        while _dirty:
            for _k in sorted(_dirty):
                while self.routes[_k] and self._intra_moves(_k):
                    pass
            self.touched = set()
            for u in range(1, self.inst.n + 1):
                if self.route_of[u] not in _dirty and not any(self.route_of[v] in _dirty for v in self.near[u]):
                    continue
                for v in self.near[u]:
                    if self.route_of[u] != self.route_of[v] and self._inter_moves(u, v):
                        break
            _dirty = self.touched


# --- construction: Solomon I1 ------------------------------------------------

def solomon_i1(inst, alpha1, lam, seed_rule):
    """Sequential I1 insertion; returns routes or None if vehicles run out."""
    search = RouteSearch(inst)
    _t = inst.t
    _unrouted = set(range(1, inst.n + 1))
    for _k in range(inst.m):
        if not _unrouted:
            break
        _single = [u for u in sorted(_unrouted) if search.feasible([u], _k)]
        if not _single:
            continue
        if seed_rule == "farthest":
            _seed = max(_single, key=lambda u: (_t[0][u], -u))
        else:
            _seed = min(_single, key=lambda u: (inst.late[u], u))
        search.insert(_seed, _k, 0)
        _unrouted.discard(_seed)
        while _unrouted:
            # c1 = alpha1 * (added travel, mu = 1) + alpha2 * (push-forward at
            # the next stop); c2 = lambda * t(depot, u) - c1.  Insert the u with
            # the largest c2 at its cheapest crossing-free position.
            _heap = []
            _options = {}
            for u in sorted(_unrouted):
                _opts = sorted(
                    (alpha1 * _add + (1.0 - alpha1) * _push, _q)
                    for _add, _push, _q in search.insertion_options(u, _k)
                )
                if _opts:
                    _options[u] = _opts
                    heapq.heappush(_heap, (-(lam * _t[0][u] - _opts[0][0]), u, 0))
            _chosen = None
            while _heap:
                _neg_c2, u, _idx = heapq.heappop(_heap)
                _q = _options[u][_idx][1]
                if search.crossing_free_insert(u, _k, _q):
                    _chosen = (u, _q)
                    break
                if _idx + 1 < len(_options[u]):
                    heapq.heappush(_heap, (-(lam * _t[0][u] - _options[u][_idx + 1][0]), u, _idx + 1))
            if _chosen is None:
                break
            search.insert(_chosen[0], _k, _chosen[1])
            _unrouted.discard(_chosen[0])
    if _unrouted:
        return None
    return search.routes


# --- ruin and recreate ---------------------------------------------------------

def _pick(rng, ranked, power):
    """Randomized choice that favors the front of a ranked list (Ropke and Pisinger)."""
    return ranked[int(len(ranked) * rng.random() ** power)]


def ruin(search, rng, count):
    """Remove customers with one of four operators; return them."""
    inst, _t = search.inst, search.inst.t
    _routed = [c for c in range(1, inst.n + 1) if search.route_of[c] >= 0]
    _op = rng.random()
    if _op < 0.1:  # route removal: empty one short route (helps use fewer vehicles)
        _active = sorted((k for k in range(inst.m) if search.routes[k]), key=lambda k: (len(search.routes[k]), k))
        _removed = list(search.routes[_pick(rng, _active, 2)])
    elif _op < 0.4:  # random removal
        _removed = rng.sample(_routed, count)
    elif _op < 0.7:  # worst removal: customers whose detour costs the most
        _saving = {}
        for c in _routed:
            _r, _p = search.routes[search.route_of[c]], search.pos_of[c]
            _a = _r[_p - 1] if _p > 0 else 0
            _b = _r[_p + 1] if _p + 1 < len(_r) else 0
            _saving[c] = _t[_a][c] + _t[c][_b] - _t[_a][_b]
        _ranked = sorted(_routed, key=lambda c: (-_saving[c], c))
        _removed = []
        while len(_removed) < count:
            c = _pick(rng, _ranked, 3)
            _ranked.remove(c)
            _removed.append(c)
    else:  # related (Shaw) removal: close in space, time, and demand
        _tmax = max(max(row) for row in _t) or 1.0
        _horizon = (max(inst.late) - min(inst.early[1:])) or 1.0
        _qmax = max(inst.demand) or 1
        _start = {c: search.starts[search.route_of[c]][search.pos_of[c]] for c in _routed}
        _removed = [rng.choice(_routed)]
        _left = [c for c in _routed if c != _removed[0]]
        while len(_removed) < count:
            _ref = rng.choice(_removed)
            _left.sort(key=lambda c: (9 * _t[_ref][c] / _tmax + 3 * abs(_start[_ref] - _start[c]) / _horizon
                                      + 2 * abs(inst.demand[_ref] - inst.demand[c]) / _qmax, c))
            _removed.append(_left.pop(int(len(_left) * rng.random() ** 6)))
    _changed = set(search.route_of[c] for c in _removed)
    for c in _removed:
        search.routes[search.route_of[c]].remove(c)
        search.route_of[c] = -1
    for _k in _changed:
        search.refresh(_k)
    return _removed


def _best_in_route(search, u, k):
    """Cheapest crossing-free feasible insertion of u in route k, or None."""
    for _add, _push, _q in sorted(search.insertion_options(u, k)):
        if search.crossing_free_insert(u, k, _q):
            return (_add, _q)
    return None


def recreate(search, removed, rng):
    """Regret-2 or greedy insertion, with or without noise (Ropke and Pisinger).

    An unused vehicle may open a new route.  Returns False if a customer
    cannot be placed anywhere.
    """
    inst = search.inst
    _regret_rule = rng.random() < 0.5
    # Noise: each insertion cost is perturbed by up to 2.5% of the longest trip.
    _noise = 0.025 * max(max(row) for row in inst.t) if rng.random() < 0.5 else 0.0
    _pending = sorted(removed)
    _active = [k for k in range(inst.m) if search.routes[k]]
    _best = {u: {k: _best_in_route(search, u, k) for k in _active} for u in _pending}
    while _pending:
        _choice = None
        for u in _pending:
            _costs = sorted((v[0] + (_noise * (2 * rng.random() - 1) if _noise else 0.0), k, v[1])
                            for k, v in _best[u].items() if v is not None)
            # Opening a new route on the first unused vehicle that can serve u.
            for k in range(inst.m):
                if not search.routes[k] and search.feasible([u], k):
                    _costs.append((inst.t[0][u] + inst.t[u][0], k, 0))
                    _costs.sort()
                    break
            if not _costs:
                return False
            if _regret_rule:
                _regret = (_costs[1][0] - _costs[0][0]) if len(_costs) > 1 else math.inf
            else:
                _regret = 0.0  # greedy: cheapest insertion first
            _key = (-_regret, _costs[0][0], u)
            if _choice is None or _key < _choice[0]:
                _choice = (_key, u, _costs[0][1], _costs[0][2])
        _, u, k, q = _choice
        search.insert(u, k, q)
        _pending.remove(u)
        for w in _pending:  # only route k changed
            _best[w][k] = _best_in_route(search, w, k)
    return True


def anneal(search, routes, cost, iterations, rng, deadline, log=None):
    """One ruin-and-recreate chain with simulated-annealing acceptance."""
    inst = search.inst
    _best_routes, _best_cost = routes, cost
    _current_routes, _current_cost = routes, cost
    _temperature = START_WORSE * cost / math.log(2)
    _cooling = 0.01 ** (1.0 / max(iterations, 1))  # ends at 1% of the start temperature
    _low = min(4, inst.n)
    _high = max(_low, min(30, int(0.3 * inst.n)))
    _stop, _best_iteration, _done = "iteration count", 0, 0
    for _it in range(1, iterations + 1):
        if time.perf_counter() > deadline:
            _stop = "time limit (safety cap)"
            break
        search.set_routes(_current_routes)
        search.touched = set()
        _removed = ruin(search, rng, rng.randint(_low, _high))
        if recreate(search, _removed, rng):
            search.local_search(dirty=search.touched)
            _cost = search.total()
            if _cost < _current_cost - EPS or rng.random() < math.exp(-(_cost - _current_cost) / _temperature):
                _current_routes, _current_cost = [r[:] for r in search.routes], _cost
                if _cost < _best_cost - EPS:
                    _best_routes, _best_cost, _best_iteration = _current_routes, _cost, _it
        _temperature *= _cooling
        _done = _it
        if log and _it % 500 == 0:
            log(f"    iteration {_it}: current {_current_cost:.3f}, best {_best_cost:.3f}")
    return _best_routes, _best_cost, {"iterations_run": _done, "best_iteration": _best_iteration,
                                      "best_cost": _best_cost, "stopping_rule": _stop}


def solve(inst, iterations=DEFAULT_ITERATIONS, chains=DEFAULT_CHAINS, seed=DEFAULT_SEED,
          time_limit=DEFAULT_TIME_LIMIT, log=None):
    """Run the researched method.  Returns (routes or None, run information)."""
    _clock = time.perf_counter()
    _deadline = _clock + time_limit
    search = RouteSearch(inst)

    # Stages 1 and 2: every I1 start, improved by local search; keep the best.
    _best_routes, _best_cost, _starts = None, math.inf, []
    for _alpha1, _lam, _seed_rule in I1_GRID:
        _routes = solomon_i1(inst, _alpha1, _lam, _seed_rule)
        _record = {"alpha1": _alpha1, "lambda": _lam, "seed_rule": _seed_rule}
        if _routes is None:
            _starts.append(dict(_record, status="ran out of vehicles"))
            continue
        search.set_routes(_routes)
        _built = search.total()
        search.local_search()
        _starts.append(dict(_record, constructed=_built, after_local_search=search.total()))
        if search.total() < _best_cost - EPS:
            _best_routes, _best_cost = [r[:] for r in search.routes], search.total()
    _info = {"method": "Solomon I1 + local search + ruin and recreate", "seed": seed, "chains": chains,
             "iterations_per_chain": iterations, "time_limit_s": time_limit, "starts": _starts}
    if _best_routes is None:
        _info.update(status="no feasible decision found", seconds=time.perf_counter() - _clock)
        return None, _info

    # Stage 3: independent annealing chains from the best start, each with
    # its own seed derived from the main seed; the best result is kept.
    _info["start_cost"] = _best_cost
    _start_routes, _start_cost = _best_routes, _best_cost
    _chain_info = []
    for _chain in range(chains):
        rng = random.Random(seed * 100 + _chain)
        _routes, _cost, _record = anneal(search, _start_routes, _start_cost, iterations, rng, _deadline, log)
        _chain_info.append(dict(_record, chain=_chain, chain_seed=seed * 100 + _chain))
        if log:
            log(f"  chain {_chain}: best {_cost:.3f}")
        if _cost < _best_cost - EPS:
            _best_routes, _best_cost = _routes, _cost
    _stops = set(c["stopping_rule"] for c in _chain_info)
    _info.update(status="feasible", chain_results=_chain_info, best_cost=_best_cost,
                 stopping_rule="time limit (safety cap)" if "time limit (safety cap)" in _stops else "iteration count",
                 seconds=time.perf_counter() - _clock)
    return {k: r for k, r in enumerate(_best_routes) if r}, _info
