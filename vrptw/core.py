"""Shared representation for the two methods (the checker does not use it).

The loader keys everything by identifier.  The methods evaluate millions of
moves, so they work on integer positions instead: node 0 is the depot and
nodes 1..n are customers in identifier order.  A route is a plain list of
customer nodes; the depot at each end is implicit (the same convention as the
class TSP helper; no in-class code is reused).
"""

EPS = 1e-9  # feasibility tolerance; the instructor's checker allows 1e-8


class Instance:
    def __init__(self, data):
        self.depot = data["depot"]
        _customer_ids = sorted(data["customers"])
        self.ids = [self.depot] + _customer_ids
        self.n = len(_customer_ids)
        _c = data["customers"]
        self.demand = [0] + [_c[i]["demand"] for i in _customer_ids]
        self.service = [0] + [_c[i]["service_time"] for i in _customer_ids]
        self.early = [0] + [_c[i]["window_start"] for i in _customer_ids]
        self.late = [0] + [_c[i]["window_end"] for i in _customer_ids]
        self.xy = [data["locations"][i] for i in self.ids]
        _t = data["travel"]
        self.t = [[_t[(a, b)] for b in self.ids] for a in self.ids]
        self.tmax = max(max(row) for row in self.t)
        # Vehicles in identifier order, as the rule to beat requires.
        self.vehicle_ids = sorted(data["vehicles"])
        _v = data["vehicles"]
        self.capacity = [_v[k]["capacity"] for k in self.vehicle_ids]
        self.shift_start = [_v[k]["shift_start"] for k in self.vehicle_ids]
        self.shift_end = [_v[k]["shift_end"] for k in self.vehicle_ids]
        self.m = len(self.vehicle_ids)


def route_cost(route, t):
    _cost, _prev = 0.0, 0
    for _c in route:
        _cost += t[_prev][_c]
        _prev = _c
    return _cost + t[_prev][0]


def schedule(route, k, inst):
    """Arrivals, service starts, and return time of route on vehicle k.

    Returns None when a window or the shift end is broken.  Capacity is
    checked separately because the load does not depend on the order.
    """
    _t, _early, _late, _service = inst.t, inst.early, inst.late, inst.service
    _time, _prev = inst.shift_start[k], 0
    _arrivals, _starts = [], []
    for _c in route:
        _arrive = _time + _t[_prev][_c]
        _start = _arrive if _arrive > _early[_c] else _early[_c]
        if _start > _late[_c] + EPS:
            return None
        _arrivals.append(_arrive)
        _starts.append(_start)
        _time, _prev = _start + _service[_c], _c
    _return = _time + _t[_prev][0]
    if _return > inst.shift_end[k] + EPS:
        return None
    return _arrivals, _starts, _return


# --- self-crossing test (the team's added constraint) -----------------------

def _orient(p, q, r):
    _v = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    return 0 if abs(_v) < 1e-12 else (1 if _v > 0 else -1)


def _on_segment(p, q, r):
    return (min(p[0], r[0]) - 1e-12 <= q[0] <= max(p[0], r[0]) + 1e-12
            and min(p[1], r[1]) - 1e-12 <= q[1] <= max(p[1], r[1]) + 1e-12)


def _same(p, q):
    return abs(p[0] - q[0]) < 1e-12 and abs(p[1] - q[1]) < 1e-12


def segments_cross(p1, p2, q1, q2):
    """True when segments p1-p2 and q1-q2 cross, overlap, or form a T.

    Two segments that only meet at a shared end point (two stops drawn at
    the same coordinates) are not counted.
    """
    _o1, _o2 = _orient(p1, p2, q1), _orient(p1, p2, q2)
    _o3, _o4 = _orient(q1, q2, p1), _orient(q1, q2, p2)
    if _o1 * _o2 < 0 and _o3 * _o4 < 0:
        return True  # proper crossing
    for _o, _point, _a, _b in ((_o1, q1, p1, p2), (_o2, q2, p1, p2), (_o3, p1, q1, q2), (_o4, p2, q1, q2)):
        if _o == 0 and _on_segment(_a, _point, _b) and not (_same(_point, _a) or _same(_point, _b)):
            return True  # an end point lies inside the other segment
    return False


def route_crosses(route, xy):
    """True when two legs of the drawn route depot -> ... -> depot cross.

    Legs that share a stop (consecutive legs, and the first and last legs,
    which share the depot) are allowed to touch at that stop.
    """
    _points = [xy[0]] + [xy[c] for c in route] + [xy[0]]
    _legs = len(_points) - 1
    if _legs < 4:
        return False  # a triangle or a there-and-back trip cannot cross itself
    # Bounding box of each leg, so most pairs are rejected without geometry.
    _box = [(min(p[0], q[0]), max(p[0], q[0]), min(p[1], q[1]), max(p[1], q[1]))
            for p, q in zip(_points, _points[1:])]
    for _a in range(_legs - 2):
        _p1, _p2 = _points[_a], _points[_a + 1]
        _x0, _x1, _y0, _y1 = _box[_a]
        for _b in range(_a + 2, _legs - (1 if _a == 0 else 0)):
            _bx0, _bx1, _by0, _by1 = _box[_b]
            if _bx0 > _x1 + 1e-12 or _bx1 < _x0 - 1e-12 or _by0 > _y1 + 1e-12 or _by1 < _y0 - 1e-12:
                continue
            if segments_cross(_p1, _p2, _points[_b], _points[_b + 1]):
                return True
    return False


def to_decision(routes, inst):
    """Convert {vehicle index: route} into the decision.json structure."""
    _out = []
    for _k in sorted(routes):
        _route = routes[_k]
        if not _route:
            continue
        _arrivals, _starts, _return = schedule(_route, _k, inst)
        _out.append({
            "vehicle_id": inst.vehicle_ids[_k],
            "visits": [inst.ids[c] for c in _route],
            "arrivals": _arrivals,
            "service_starts": _starts,
            "return_time": _return,
        })
    return {"routes": _out}
