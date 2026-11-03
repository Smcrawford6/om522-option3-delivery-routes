"""Method 1, the rule to beat: nearest feasible neighbor, one vehicle at a time.

Implemented exactly as option-3-brief.pdf states it:
  * vehicles are taken in identifier order, each leaving the depot at its
    shift start;
  * the vehicle repeatedly moves to the nearest unserved customer (travel
    time from the current location, ties by customer identifier) that fits
    the remaining capacity, can start service by its window end, and still
    allows a return to the depot by the shift end;
  * when no customer qualifies the vehicle returns and the next one starts;
  * a customer still unserved after every vehicle returns means
    "no feasible decision found" (returns None).
The rule is deterministic and has no seed.  It does not apply the team's
no-self-crossing constraint, because the guide requires the rule as written.
"""

from .core import EPS


def nearest_feasible_neighbor(inst):
    _t, _demand, _service = inst.t, inst.demand, inst.service
    _early, _late = inst.early, inst.late
    # Customer nodes are numbered in identifier order, so the smaller node
    # wins a travel-time tie, i.e., ties go by customer identifier.
    _unserved = set(range(1, inst.n + 1))
    _routes = {}
    for _k in range(inst.m):  # vehicles in identifier order
        if not _unserved:
            break
        _time, _here, _room = inst.shift_start[_k], 0, inst.capacity[_k]
        _route = []
        while True:
            _best, _best_key = None, None
            for _c in _unserved:
                if _demand[_c] > _room:
                    continue
                _arrive = _time + _t[_here][_c]
                if _arrive > _late[_c] + EPS:  # cannot start service by window end
                    continue
                _start = max(_arrive, _early[_c])
                if _start + _service[_c] + _t[_c][0] > inst.shift_end[_k] + EPS:
                    continue  # could not get back to the depot in time
                _key = (_t[_here][_c], _c)
                if _best_key is None or _key < _best_key:
                    _best, _best_key = _c, _key
            if _best is None:
                break  # no customer qualifies: return to the depot
            _start = max(_time + _t[_here][_best], _early[_best])
            _route.append(_best)
            _unserved.discard(_best)
            _room -= _demand[_best]
            _time, _here = _start + _service[_best], _best
        if _route:
            _routes[_k] = _route
    if _unserved:
        return None
    return _routes
