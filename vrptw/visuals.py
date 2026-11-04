"""README figures and the project website's data (python -m vrptw site).

Everything here is read from the submitted results: the decisions in
results/decisions/, the comparison table, the stress results, and the
convergence traces in results/convergence/ (python -m vrptw traces reruns the
researched method with its default seed to record them; the rerun reproduces
the submitted decision exactly, which is checked).  Nothing here changes a
decision or a measure.

Outputs:
  docs/img/*.png, docs/img/pipeline.svg   figures used by README.md and the site
  docs/data/cases.js                      every instance, both plans, and the
                                          traces, for docs/index.html
"""

import csv
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

from . import researched  # noqa: E402
from .checker import check_decision  # noqa: E402
from .core import Instance  # noqa: E402
from .experiments import (COLOR, CROSSING, GRID, INK, INSTANCES, METHODS, MUTED, RESULTS, ROOT,  # noqa: E402
                          STRESS_INSTANCE, _decision_path, _style)
from .loader import load_instance  # noqa: E402

DOCS = ROOT / "docs"
IMG = DOCS / "img"
TRACES = RESULTS / "convergence"
ALL_CASES = INSTANCES + ["edge_case"]
LABEL = {"hand_checkable": "Hand-checkable", "development_small": "Small", "development_medium": "Medium",
         "development_large": "Large", "edge_case": "Edge case"}
# Timeline segments (validated: CVD and normal-vision separation pass, contrast >= 3:1).
DRIVE, SERVICE, WAIT_EDGE = "#2f6fa6", "#b37700", "#b9b8b2"
CRIMSON_TINT = "#d98c99"  # intermediate stages, lighter step of the crimson
TRACE_EVERY = 10          # site traces keep every 10th iteration (plus every new best)


# --- convergence traces (slow: reruns the researched method) ----------------------

def traces():
    """Rerun the researched method with its defaults and record every chain's
    current and best cost after each iteration."""
    TRACES.mkdir(parents=True, exist_ok=True)
    for _name in INSTANCES:
        data = load_instance(ROOT / _name)
        print(f"{_name}: recording convergence ...", flush=True)
        _trace = []
        _routes, _info = researched.solve(Instance(data), trace=_trace)
        with open(_decision_path(_name, "researched"), encoding="utf-8") as _f:
            _submitted = check_decision(data, json.load(_f))["measures"]["total_travel_time"]
        if abs(_info["best_cost"] - _submitted) > 1e-3:
            raise RuntimeError(f"{_name}: traced run ended at {_info['best_cost']:.3f}, "
                               f"submitted decision has {_submitted:.3f}")
        _chains = []
        for _chain in _trace:
            _keep, _last_best = [], math.inf
            for _it, _current, _best in _chain:
                if _it % TRACE_EVERY == 0 or _best < _last_best - 1e-9 or _it == 1:
                    _keep.append([_it, round(_current, 3), round(_best, 3)])
                _last_best = _best
            _chains.append(_keep)
        _built = [s["constructed"] for s in _info["starts"] if "constructed" in s]
        with open(TRACES / f"{_name}.json", "w", encoding="utf-8", newline="\n") as _f:
            json.dump({"instance": _name, "seed": _info["seed"], "iterations_per_chain": _info["iterations_per_chain"],
                       "best_constructed": round(min(_built), 3) if _built else None,
                       "start_cost": round(_info["start_cost"], 3), "best_cost": round(_info["best_cost"], 3),
                       "chains": _chains}, _f)
    print(f"saved convergence traces to {TRACES.relative_to(ROOT)}")


# --- shared loading -------------------------------------------------------------------

def _comparison_rows():
    with open(RESULTS / "comparison.csv", newline="", encoding="utf-8") as _f:
        return {(r["instance"], r["method"]): r for r in csv.DictReader(_f)}


def _reports(name):
    data = load_instance(ROOT / name)
    _out = {}
    for _method in METHODS:
        _path = _decision_path(name, _method)
        if _path.exists():
            with open(_path, encoding="utf-8") as _f:
                _out[_method] = check_decision(data, json.load(_f))
    return data, _out


def _trace(name):
    _path = TRACES / f"{name}.json"
    if not _path.exists():
        return None
    with open(_path, encoding="utf-8") as _f:
        return json.load(_f)


def _segments(data, route):
    """Driving, waiting, and service intervals of one checked route, in minutes."""
    _vehicle = data["vehicles"][route["vehicle_id"]]
    _time, _out = _vehicle["shift_start"], []
    for _c, _arrive, _start in zip(route["visits"], route["arrivals"], route["service_starts"]):
        _out.append(("drive", _time, _arrive, _c))
        if _start > _arrive + 1e-9:
            _out.append(("wait", _arrive, _start, _c))
        _end = _start + data["customers"][_c]["service_time"]
        _out.append(("service", _start, _end, _c))
        _time = _end
    _out.append(("drive", _time, route["return_time"], data["depot"]))
    return _out


def _save(fig, name):
    IMG.mkdir(parents=True, exist_ok=True)
    fig.savefig(IMG / name, dpi=150, facecolor="white")
    plt.close(fig)


def _short(method):
    return METHODS[method].split(" (")[0]


# --- figures ---------------------------------------------------------------------------

def _plot_trucks(name, data, report):
    """One small panel per truck of the researched plan, stops numbered in order."""
    _loc, _depot = data["locations"], data["depot"]
    _routes = report["routes"]
    _cols = min(5, len(_routes))
    _rows = math.ceil(len(_routes) / _cols)
    fig, axes = plt.subplots(_rows, _cols, figsize=(2.6 * _cols, 3.05 * _rows + 0.5), squeeze=False)
    _xs = [p[0] for p in _loc.values()]
    _ys = [p[1] for p in _loc.values()]
    _pad = 0.06 * max(max(_xs) - min(_xs), max(_ys) - min(_ys))
    for _i, ax in enumerate(axes.flat):
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_aspect("equal")
        ax.set_xlim(min(_xs) - _pad, max(_xs) + _pad)
        ax.set_ylim(min(_ys) - _pad, max(_ys) + _pad)
        for _s in ax.spines.values():
            _s.set_color(GRID)
        if _i >= len(_routes):
            ax.set_visible(False)
            continue
        _route = _routes[_i]
        _vehicle = data["vehicles"][_route["vehicle_id"]]
        ax.scatter([_loc[c][0] for c in data["customers"]], [_loc[c][1] for c in data["customers"]], s=6,
                   color=GRID, zorder=1)
        _pts = [_loc[s] for s in [_depot] + _route["visits"] + [_depot]]
        ax.plot([p[0] for p in _pts], [p[1] for p in _pts], color=COLOR["researched"], linewidth=1.6, zorder=2)
        for _n, _c in enumerate(_route["visits"], 1):
            ax.scatter([_loc[_c][0]], [_loc[_c][1]], s=95, color="white", edgecolor=COLOR["researched"],
                       linewidth=1.1, zorder=3)
            ax.text(_loc[_c][0], _loc[_c][1], str(_n), ha="center", va="center", fontsize=6, color=INK, zorder=4)
        ax.scatter([_loc[_depot][0]], [_loc[_depot][1]], s=55, marker="s", color=INK, zorder=5)
        ax.set_title(f"{_route['vehicle_id']}: {len(_route['visits'])} stops, {_route['travel_time']:.0f} min\n"
                     f"load {_route['load']}/{_vehicle['capacity']}, back at {_route['return_time']:.0f}",
                     fontsize=8, color=INK, loc="left")
    fig.suptitle(f"{LABEL[name]} case, researched plan, one panel per truck (numbers = visiting order, "
                 f"black square = depot)", fontsize=10, color=MUTED, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    _save(fig, f"trucks_{name}.png")


def _plot_timeline(name, data, reports):
    """Each truck's day for both plans: driving, waiting, service, and the time windows."""
    _n = max(len(r["routes"]) for r in reports.values())
    _end = max(v["shift_end"] for v in data["vehicles"].values())
    fig, axes = plt.subplots(1, 2, figsize=(13, 0.34 * _n + 1.9), sharex=True)
    for ax, _method in zip(axes, METHODS):
        report = reports[_method]
        for _row, _route in enumerate(report["routes"]):
            for _kind, _a, _b, _c in _segments(data, _route):
                if _kind == "wait":
                    ax.add_patch(Rectangle((_a, _row - 0.28), _b - _a, 0.56, facecolor="white", edgecolor=WAIT_EDGE,
                                           hatch="////", linewidth=0.6))
                else:
                    ax.add_patch(Rectangle((_a, _row - 0.28), _b - _a, 0.56,
                                           facecolor=DRIVE if _kind == "drive" else SERVICE, edgecolor="white",
                                           linewidth=0.5))
            for _c in _route["visits"]:
                _cust = data["customers"][_c]
                ax.plot([_cust["window_start"], _cust["window_end"]], [_row - 0.40] * 2, color=INK, linewidth=0.7,
                        alpha=0.45, solid_capstyle="butt")
        ax.axvline(_end, color=MUTED, linewidth=1)
        ax.set_yticks(range(len(report["routes"])), [r["vehicle_id"] for r in report["routes"]], fontsize=8)
        ax.set_ylim(_n - 0.4, -0.7)
        ax.set_xlim(0, _end * 1.02)
        _style(ax)
        ax.grid(axis="x", color=GRID, linewidth=0.8)
        ax.grid(axis="y", visible=False)
        _m = report["measures"]
        ax.set_title(f"{_short(_method)}: {_m['vehicles_used']} trucks, {_m['total_travel_time']:.0f} min driving, "
                     f"{_m['waiting_time']:.0f} min waiting", fontsize=10, color=INK, loc="left")
        ax.set_xlabel("Minutes after the shift starts (vertical line = shift end)", fontsize=9, color=MUTED)
    _handles = [Rectangle((0, 0), 1, 1, facecolor=DRIVE), Rectangle((0, 0), 1, 1, facecolor=SERVICE),
                Rectangle((0, 0), 1, 1, facecolor="white", edgecolor=WAIT_EDGE, hatch="////"),
                plt.Line2D([0], [0], color=INK, alpha=0.45, linewidth=0.8)]
    fig.legend(_handles, ["Driving", "Service at a customer", "Waiting for a window to open",
                          "Customer time window (thin line above the bar)"],
               loc="lower left", ncol=4, frameon=False, fontsize=9, bbox_to_anchor=(0.01, 0.0))
    fig.suptitle(f"{LABEL[name]} case: each truck's day", fontsize=11, color=INK, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0.05, 1, 0.97))
    _save(fig, f"timeline_{name}.png")


def _plot_convergence(traces_by_case, rows):
    # hand_checkable is left out: its start is already the best plan found, so its panel is flat.
    _cases = [n for n in INSTANCES if traces_by_case.get(n) and n != "hand_checkable"]
    fig, axes = plt.subplots(1, len(_cases), figsize=(3.4 * len(_cases), 3.6))
    for ax, _name in zip(axes, _cases):
        _t = traces_by_case[_name]
        _style(ax)
        for _j, _chain in enumerate(_t["chains"]):
            _it = [p[0] for p in _chain]
            if _j == 0:
                ax.plot(_it, [p[1] for p in _chain], color=COLOR["researched"], alpha=0.18, linewidth=1,
                        label="Chain 1, cost it is currently at")
            ax.plot(_it, [p[2] for p in _chain], color=COLOR["researched"], linewidth=1.8, alpha=0.55 + 0.15 * (_j == 0),
                    label="Best so far, each of the 4 chains" if _j == 0 else None)
        ax.axhline(_t["start_cost"], color=MUTED, linewidth=1)
        ax.text(1.1, _t["start_cost"], f"start {_t['start_cost']:,.0f}", fontsize=8, color=MUTED, va="bottom")
        ax.set_xscale("log")
        ax.set_xlim(1, _t["iterations_per_chain"])
        _lo = _t["best_cost"]
        _hi = max(max(p[1] for p in c) for c in _t["chains"])
        ax.set_ylim(_lo - 0.04 * (_hi - _lo + 1), _hi + 0.06 * (_hi - _lo + 1))
        _rule = float(rows[(_name, "rule")]["total_travel_time"])
        ax.set_title(f"{LABEL[_name]}: ends at {_lo:,.0f} min\n(rule to beat: {_rule:,.0f})", fontsize=10,
                     color=INK, loc="left")
        ax.set_xlabel("Ruin-and-recreate iteration (log scale)", fontsize=8, color=MUTED)
    axes[0].set_ylabel("Total travel (min)", fontsize=9, color=MUTED)
    axes[0].legend(frameon=False, fontsize=8, loc="upper right")
    fig.tight_layout()
    _save(fig, "convergence.png")


def _plot_stages(traces_by_case, rows):
    """Where the saving comes from: rule, then each stage of the researched method."""
    _cases = [n for n in INSTANCES if traces_by_case.get(n)]
    fig, axes = plt.subplots(1, len(_cases), figsize=(3.4 * len(_cases), 3.5))
    _labels = ["Rule to\nbeat", "Solomon I1\n(best of 12)", "+ local\nsearch", "+ ruin and\nrecreate"]
    for ax, _name in zip(axes, _cases):
        _t = traces_by_case[_name]
        _vals = [float(rows[(_name, "rule")]["total_travel_time"]), _t["best_constructed"], _t["start_cost"],
                 _t["best_cost"]]
        _style(ax)
        ax.bar(range(4), _vals, width=0.62, color=[COLOR["rule"], CRIMSON_TINT, CRIMSON_TINT, COLOR["researched"]],
               edgecolor="white", linewidth=2)
        for _i, _v in enumerate(_vals):
            ax.text(_i, _v, f"{_v:,.0f}", ha="center", va="bottom", fontsize=8, color=INK)
        ax.set_xticks(range(4), _labels, fontsize=7.5)
        _saving = 100 * (_vals[0] - _vals[3]) / _vals[0]
        ax.set_title(f"{LABEL[_name]}: {_saving:.1f}% less travel", fontsize=10, color=INK, loc="left")
        ax.set_ylim(0, _vals[0] * 1.14)
    axes[0].set_ylabel("Total travel (min)", fontsize=9, color=MUTED)
    fig.tight_layout()
    _save(fig, "stages.png")


def _plot_stress():
    with open(RESULTS / "stress" / "stress_results.csv", newline="", encoding="utf-8") as _f:
        _rows = list(csv.DictReader(_f))
    with open(RESULTS / "stress" / "stress_summary.json", encoding="utf-8") as _f:
        _summary = json.load(_f)["summary"]
    fig, ax = plt.subplots(figsize=(11, 3.4))
    _style(ax)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    for _j, _method in enumerate(["researched", "rule"]):
        _mine = [r for r in _rows if r["method"] == _method]
        for _k, _r in enumerate(sorted(_mine, key=lambda r: float(r["total_travel_time"]))):
            _y = _j + ((_k % 5) - 2) * 0.07
            _bad = int(_r["violations"]) > 0
            ax.scatter([float(_r["total_travel_time"])], [_y], s=46,
                       color="white" if _bad else COLOR[_method], edgecolor=COLOR[_method] if not _bad else INK,
                       linewidth=1.4 if _bad else 0.8, zorder=3)
        _plan = _summary[_method]["planned_travel"]
        ax.plot([_plan, _plan], [_j - 0.3, _j + 0.3], color=INK, linewidth=2, zorder=4)
        ax.text(_plan, _j - 0.33, f"planned {_plan:,.0f}", ha="center", va="bottom", fontsize=8, color=INK)
    ax.set_yticks([0, 1], ["Researched", "Rule to beat"], fontsize=10)
    ax.set_ylim(1.45, -0.6)
    ax.set_xlabel("Realized total travel on one simulated day (min). One dot per scenario; hollow dot with a dark "
                  "ring = at least one late service or late return", fontsize=9, color=MUTED)
    ax.set_title(f"{LABEL[STRESS_INSTANCE]} case under 30 random traffic days: the saving holds", fontsize=11,
                 color=INK, loc="left")
    fig.tight_layout()
    _save(fig, "stress_strip.png")

    with open(RESULTS / "stress" / "sensitivity.csv", newline="", encoding="utf-8") as _f:
        _sens = list(csv.DictReader(_f))
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.5))
    for ax, (_key, _title) in zip(axes, (("scenarios_with_violation", "Days (of 30) with at least one violation"),
                                         ("late_returns_total", "Late returns to the depot, total"),
                                         ("lateness_mean_min", "Minutes late per day, mean"))):
        _style(ax)
        for _method in METHODS:
            _mine = [r for r in _sens if r["method"] == _method]
            _x = [float(r["mean_congestion"]) for r in _mine]
            _y = [float(r[_key]) for r in _mine]
            ax.plot(_x, _y, color=COLOR[_method], linewidth=2, marker="o", markersize=6, label=_short(_method))
            ax.text(_x[-1] + 0.015, _y[-1], f"{_y[-1]:.0f}" if _key != "lateness_mean_min" else f"{_y[-1]:.1f}",
                    fontsize=8, color=INK, va="center")
        ax.set_xticks(_x, [f"{v:.1f}x" for v in _x])
        ax.set_xlim(0.97, 1.36)
        ax.set_title(_title, fontsize=10, color=INK, loc="left")
        ax.set_xlabel("Average traffic level (1.0x = as planned)", fontsize=8, color=MUTED)
    axes[0].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    _save(fig, "sensitivity.png")


def _plot_edge_case(data):
    _cap = max(v["capacity"] for v in data["vehicles"].values())
    _ids = sorted(data["customers"])
    _dem = [data["customers"][c]["demand"] for c in _ids]
    fig, ax = plt.subplots(figsize=(8, 3.2))
    _style(ax)
    ax.bar(range(len(_ids)), _dem, width=0.62, edgecolor="white", linewidth=2,
           color=[COLOR["researched"] if d > _cap else COLOR["rule"] for d in _dem])
    ax.axhline(_cap, color=INK, linewidth=1.2)
    ax.text(-0.4, _cap + 1, f"largest truck holds {_cap}", ha="left", va="bottom", fontsize=9, color=INK)
    for _i, _d in enumerate(_dem):
        if _d > _cap:
            ax.text(_i, _d, f"{_ids[_i]} needs {_d}", ha="center", va="bottom", fontsize=9, color=INK)
    ax.set_xticks(range(len(_ids)), _ids, fontsize=8)
    ax.set_ylim(0, max(_dem) * 1.2)
    ax.set_ylabel("Demand (units)", fontsize=9, color=MUTED)
    ax.set_title("Edge case: one order is bigger than any truck, so no plan can serve every customer",
                 fontsize=10, color=INK, loc="left")
    fig.tight_layout()
    _save(fig, "edge_case.png")


def _pipeline_svg(trace, rule_cost):
    """The method at a glance, with the medium case's numbers."""
    _steps = [
        ("1", "Solomon I1 build", "12 starting plans", f"best {trace['best_constructed']:,.0f} min"),
        ("2", "Local search", "5 kinds of moves", f"{trace['start_cost']:,.0f} min"),
        ("3", "Ruin and recreate", "4 chains x 2,000 iterations", f"{trace['best_cost']:,.0f} min"),
    ]
    _box = []
    for _i, (_n, _title, _sub, _val) in enumerate(_steps):
        _x = 250 + _i * 200
        _box.append(f'''
  <g transform="translate({_x},150)">
    <rect width="182" height="96" rx="10" fill="#ffffff" stroke="#9e1b32" stroke-width="1.5"/>
    <circle cx="22" cy="24" r="12" fill="#9e1b32"/><text x="22" y="28.5" class="n">{_n}</text>
    <text x="42" y="29" class="t">{_title}</text>
    <text x="14" y="58" class="s">{_sub}</text>
    <text x="14" y="82" class="v">{_val}</text>
  </g>''')
        if _i < 2:
            _box.append(f'<path d="M{_x + 184} 198 h14" class="arrow"/>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 300" width="960" height="300" role="img"
     aria-label="How the tool works: input checks, then the rule to beat or the three-stage researched method, then the independent checker">
  <style>
    text {{ font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; fill: #0b0b0b; }}
    .h {{ font-size: 15px; font-weight: 700; }}
    .t {{ font-size: 13px; font-weight: 700; }}
    .s {{ font-size: 12px; fill: #52514e; }}
    .v {{ font-size: 15px; font-weight: 700; fill: #9e1b32; }}
    .vg {{ font-size: 15px; font-weight: 700; fill: #5d6468; }}
    .n {{ font-size: 12px; font-weight: 700; fill: #ffffff; text-anchor: middle; }}
    .arrow {{ stroke: #52514e; stroke-width: 1.5; fill: none; marker-end: url(#a); }}
  </style>
  <defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
    <path d="M0 0 L10 5 L0 10 z" fill="#52514e"/></marker></defs>
  <rect width="960" height="300" rx="14" fill="#f7f6f3"/>
  <text x="24" y="34" class="h">How one planning run works (numbers: medium case, 45 customers)</text>
  <g transform="translate(24,96)">
    <rect width="176" height="150" rx="10" fill="#ffffff" stroke="#c9c8c2"/>
    <text x="14" y="28" class="t">Day's input files</text>
    <text x="14" y="52" class="s">customers, trucks,</text>
    <text x="14" y="68" class="s">depot, travel times</text>
    <text x="14" y="100" class="t">Four input checks</text>
    <text x="14" y="122" class="s">bad file? clear error,</text>
    <text x="14" y="138" class="s">exit status 2</text>
  </g>
  <path d="M202 140 C226 140 214 104 246 98" class="arrow"/>
  <path d="M202 200 h44" class="arrow"/>
  <g transform="translate(250,64)">
    <rect width="582" height="56" rx="10" fill="#ffffff" stroke="#828a8f" stroke-width="1.5"/>
    <text x="14" y="24" class="t">Rule to beat: nearest feasible neighbor</text>
    <text x="14" y="44" class="s">each truck drives to the closest customer that still fits; never revisits a choice</text>
    <text x="568" y="36" class="vg" text-anchor="end">{rule_cost:,.0f} min</text>
  </g>
  <text x="250" y="140" class="s">Researched method (what <tspan font-weight="700">pixi run solve</tspan> runs): every move is checked against every rule, including no self-crossing</text>
  {"".join(_box)}
  <path d="M834 92 C884 92 896 140 896 168" class="arrow"/>
  <path d="M834 210 h10" class="arrow"/>
  <g transform="translate(846,172)">
    <rect width="100" height="74" rx="10" fill="#0b0b0b"/>
    <text x="50" y="30" class="n">Independent</text>
    <text x="50" y="46" class="n">checker</text>
    <text x="50" y="62" class="n" font-weight="400">decision.json</text>
  </g>
  <text x="24" y="282" class="s">The checker shares no code with either method and recomputes every arrival, load, and measure from the visit lists.</text>
</svg>
'''


# --- website data --------------------------------------------------------------------

def _case_data(name, data, reports, rows, trace):
    _loc = data["locations"]
    _max_cap = max(v["capacity"] for v in data["vehicles"].values())
    _case = {
        "id": name, "label": LABEL[name], "customers_n": len(data["customers"]),
        "depot": {"id": data["depot"], "x": _loc[data["depot"]][0], "y": _loc[data["depot"]][1]},
        "customers": [{"id": c, "x": _loc[c][0], "y": _loc[c][1], "demand": v["demand"], "service": v["service_time"],
                       "ws": v["window_start"], "we": v["window_end"]} for c, v in sorted(data["customers"].items())],
        "vehicles": [{"id": k, "capacity": v["capacity"], "start": v["shift_start"], "end": v["shift_end"]}
                     for k, v in sorted(data["vehicles"].items())],
        "too_big": [c for c, v in sorted(data["customers"].items()) if v["demand"] > _max_cap],
        "methods": {},
    }
    for _method in METHODS:
        _row = rows[(name, _method)]
        _entry = {"status": _row["status"], "seconds": float(_row["computation_time_s"])}
        if _method in reports:
            _r = reports[_method]
            _entry["checker"] = "feasible" if _r["feasible"] else "INFEASIBLE"
            _entry["measures"] = {k: (round(v, 3) if isinstance(v, float) else v) for k, v in _r["measures"].items()}
            _entry["routes"] = [{
                "vehicle": rt["vehicle_id"], "visits": rt["visits"],
                "arrivals": [round(a, 3) for a in rt["arrivals"]], "starts": [round(s, 3) for s in rt["service_starts"]],
                "ret": round(rt["return_time"], 3), "load": rt["load"], "travel": round(rt["travel_time"], 3),
                "wait": round(rt["waiting_time"], 3), "crossings": rt["self_crossings"]} for rt in _r["routes"]]
        _case["methods"][_method] = _entry
    if trace:
        _case["convergence"] = {k: trace[k] for k in ("best_constructed", "start_cost", "best_cost",
                                                      "iterations_per_chain", "chains")}
    return _case


def _stress_data():
    with open(RESULTS / "stress" / "stress_results.csv", newline="", encoding="utf-8") as _f:
        _rows = [{k: (float(v) if k not in ("method",) else v) for k, v in r.items()} for r in csv.DictReader(_f)]
    with open(RESULTS / "stress" / "sensitivity.csv", newline="", encoding="utf-8") as _f:
        _sens = [{k: (float(v) if k != "method" else v) for k, v in r.items()} for r in csv.DictReader(_f)]
    with open(RESULTS / "stress" / "stress_summary.json", encoding="utf-8") as _f:
        _summary = json.load(_f)
    return {"instance": STRESS_INSTANCE, "label": LABEL[STRESS_INSTANCE], "scenarios": _rows, "sensitivity": _sens,
            "summary": _summary}


def site():
    """Build every README figure and docs/data/cases.js from the saved results."""
    rows = _comparison_rows()
    _traces = {n: _trace(n) for n in INSTANCES}
    if not all(_traces.values()):
        print("note: convergence traces missing; run `python -m vrptw traces` for the convergence figures")
    _cases = []
    for _name in ALL_CASES:
        data, reports = _reports(_name)
        if len(reports) == len(METHODS):
            _plot_trucks(_name, data, reports["researched"])
            _plot_timeline(_name, data, reports)
        if _name == "edge_case":
            _plot_edge_case(data)
        _cases.append(_case_data(_name, data, reports, rows, _traces.get(_name)))
    if all(_traces.values()):
        _plot_convergence(_traces, rows)
        _plot_stages(_traces, rows)
        (IMG / "pipeline.svg").write_text(
            _pipeline_svg(_traces["development_medium"], float(rows[("development_medium", "rule")]["total_travel_time"])),
            encoding="utf-8", newline="\n")
    _plot_stress()
    (DOCS / "data").mkdir(parents=True, exist_ok=True)
    _payload = {"cases": _cases, "stress": _stress_data(),
                "colors": {"rule": COLOR["rule"], "researched": COLOR["researched"], "crossing": CROSSING}}
    (DOCS / "data" / "cases.js").write_text(
        "// Generated by `python -m vrptw site` from results/. Do not edit by hand.\n"
        "window.PROJECT_DATA = " + json.dumps(_payload, separators=(",", ":")) + ";\n",
        encoding="utf-8", newline="\n")
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    print("wrote docs/img/* and docs/data/cases.js")
