"""Independent solution checker.

Reads only the input files (through the loader) and a decision.json file,
and recomputes every time and measure from the visit lists.  It shares no
code with either method: it works on identifiers and the loader's
dictionaries, and it has its own timing and crossing geometry, so a bug in
a method cannot also hide itself here.
"""

import json
import math

TOL = 1e-8  # the instructor's tolerance at every window and shift end


def _ccw(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _legs_cross(a, b, c, d):
    """Proper crossing, overlap, or T-junction of legs a-b and c-d."""
    _d1, _d2, _d3, _d4 = _ccw(a, b, c), _ccw(a, b, d), _ccw(c, d, a), _ccw(c, d, b)
    _z = 1e-12
    if ((_d1 > _z and _d2 < -_z) or (_d1 < -_z and _d2 > _z)) and \
       ((_d3 > _z and _d4 < -_z) or (_d3 < -_z and _d4 > _z)):
        return True

    def _inside(p, q, r):  # r on segment p-q, away from both end points
        return (abs(_ccw(p, q, r)) <= _z
                and min(p[0], q[0]) - _z <= r[0] <= max(p[0], q[0]) + _z
                and min(p[1], q[1]) - _z <= r[1] <= max(p[1], q[1]) + _z
                and math.dist(r, p) > _z and math.dist(r, q) > _z)

    return _inside(a, b, c) or _inside(a, b, d) or _inside(c, d, a) or _inside(c, d, b)


def count_self_crossings(stops, locations):
    """Pairs of non-adjacent legs of one drawn route that cross."""
    _points = [locations[s] for s in stops]
    _legs = [(_points[i], _points[i + 1]) for i in range(len(_points) - 1)]
    _count = 0
    for _i in range(len(_legs)):
        for _j in range(_i + 2, len(_legs)):
            if _i == 0 and _j == len(_legs) - 1:
                continue  # first and last legs share the depot
            if _legs_cross(*_legs[_i], *_legs[_j]):
                _count += 1
    return _count


def check_decision(data, decision):
    """Return a report with violations, team-constraint findings, and measures."""
    _depot, _customers, _vehicles = data["depot"], data["customers"], data["vehicles"]
    _travel = data["travel"]
    _violations, _warnings = [], []
    _served = {}
    _used_vehicles = set()
    _route_reports = []
    _total_travel = _total_wait = 0.0
    _crossing_total = 0

    _routes = decision.get("routes") if isinstance(decision, dict) else None
    if not isinstance(_routes, list):
        return {"feasible": False, "violations": ["decision has no 'routes' list"], "warnings": [],
                "routes": [], "measures": {}}

    for _n, _route in enumerate(_routes):
        if not isinstance(_route, dict):
            _violations.append(f"route {_n}: is not an object with vehicle_id and visits")
            continue
        _vid = _route.get("vehicle_id")
        _visits = _route.get("visits")
        if not isinstance(_vid, str) or _vid not in _vehicles:
            _violations.append(f"route {_n}: vehicle '{_vid}' is not in vehicles.csv")
            continue
        if _vid in _used_vehicles:
            _violations.append(f"vehicle {_vid}: makes more than one route")
        _used_vehicles.add(_vid)
        if not isinstance(_visits, list) or not _visits:
            _violations.append(f"vehicle {_vid}: route has no visits")
            continue
        _vehicle = _vehicles[_vid]
        _time, _here, _load, _travel_r, _wait_r = _vehicle["shift_start"], _depot, 0, 0.0, 0.0
        _arrivals, _starts = [], []
        for _c in _visits:
            if not isinstance(_c, str) or _c not in _customers:
                _violations.append(f"vehicle {_vid}: visit '{_c}' is not in customers.csv")
                break
            _served[_c] = _served.get(_c, 0) + 1
            _cust = _customers[_c]
            _leg = _travel[(_here, _c)]
            _arrive = _time + _leg
            _start = max(_arrive, _cust["window_start"])
            if _start > _cust["window_end"] + TOL:
                _violations.append(
                    f"vehicle {_vid}: service at {_c} starts at {_start:.3f}, after its window end {_cust['window_end']}")
            _load += _cust["demand"]
            _travel_r += _leg
            _wait_r += _start - _arrive
            _arrivals.append(_arrive)
            _starts.append(_start)
            _time, _here = _start + _cust["service_time"], _c
        else:
            _leg = _travel[(_here, _depot)]
            _travel_r += _leg
            _return = _time + _leg
            if _return > _vehicle["shift_end"] + TOL:
                _violations.append(
                    f"vehicle {_vid}: returns at {_return:.3f}, after its shift end {_vehicle['shift_end']}")
            if _load > _vehicle["capacity"]:
                _violations.append(f"vehicle {_vid}: load {_load} exceeds capacity {_vehicle['capacity']}")
            # Reported times are informational (the instructor recomputes them),
            # but a mismatch means the method's own bookkeeping is wrong.
            for _key, _mine in (("arrivals", _arrivals), ("service_starts", _starts)):
                _theirs = _route.get(_key)
                if _theirs is not None and (len(_theirs) != len(_mine) or any(
                        abs(a - b) > 1e-6 for a, b in zip(_theirs, _mine))):
                    _warnings.append(f"vehicle {_vid}: reported {_key} differ from recomputed values")
            if _route.get("return_time") is not None and abs(_route["return_time"] - _return) > 1e-6:
                _warnings.append(f"vehicle {_vid}: reported return_time differs from recomputed value")
            _crossings = count_self_crossings([_depot] + _visits + [_depot], data["locations"])
            _crossing_total += _crossings
            _total_travel += _travel_r
            _total_wait += _wait_r
            _route_reports.append({
                "vehicle_id": _vid, "visits": _visits, "arrivals": _arrivals, "service_starts": _starts,
                "return_time": _return, "load": _load, "travel_time": _travel_r, "waiting_time": _wait_r,
                "self_crossings": _crossings,
            })

    for _c in sorted(_customers):
        if _served.get(_c, 0) == 0:
            _violations.append(f"customer {_c}: not served")
        elif _served[_c] > 1:
            _violations.append(f"customer {_c}: served {_served[_c]} times")

    return {
        "feasible": not _violations,
        "violations": _violations,
        "warnings": _warnings,
        "routes": _route_reports,
        "measures": {
            "total_travel_time": _total_travel,
            "vehicles_used": len(_route_reports),
            "waiting_time": _total_wait,
            "customers_served": sum(1 for _c in _served if _c in _customers),
            "self_crossings": _crossing_total,
        },
    }


def check_file(data, decision_path):
    with open(decision_path, encoding="utf-8") as _f:
        return check_decision(data, json.load(_f))
