"""Deterministic comparison, stress test, and figures (python -m vrptw reproduce)."""

import csv
import json
import math
import random
import statistics
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker  # noqa: E402

from . import researched  # noqa: E402
from .checker import check_decision  # noqa: E402
from .cli import machine, run_method  # noqa: E402
from .loader import load_instance  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
INSTANCES = ["hand_checkable", "development_small", "development_medium", "development_large"]
METHODS = {"rule": "Rule to beat (nearest feasible neighbor)",
           "researched": "Researched (Solomon I1 + local search + ruin and recreate)"}
COLOR = {"rule": "#828a8f", "researched": "#9e1b32"}  # University of Alabama gray and crimson
CROSSING = "#16181d"  # dashed near-black, so it never reads as either method
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"

# Stress test: uncertain travel times (brief: "a congestion factor per scenario").
STRESS_INSTANCE = "development_medium"
STRESS_SEED = 20261103
SCENARIOS = 30
CONGESTION_CV = 0.15  # one day-wide congestion factor per scenario, lognormal, mean 1
LEG_CV = 0.10         # an independent factor on every ordered leg, lognormal, mean 1


def _style(ax):
    for _side in ("top", "right"):
        ax.spines[_side].set_visible(False)
    for _side in ("left", "bottom"):
        ax.spines[_side].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _decision_path(instance, method):
    return RESULTS / "decisions" / instance / method / "decision.json"


# --- deterministic comparison --------------------------------------------------

def compare():
    _rows = []
    for _name in INSTANCES + ["edge_case"]:
        data = load_instance(ROOT / _name)
        for _method in METHODS:
            print(f"{_name}: {_method} ...", flush=True)
            decision, info, seconds = run_method(data, _method)
            _path = _decision_path(_name, _method)
            _path.parent.mkdir(parents=True, exist_ok=True)
            _path.unlink(missing_ok=True)
            _row = {"instance": _name, "customers": len(data["customers"]), "method": _method,
                    "computation_time_s": round(seconds, 3), "stopping_rule": info.get("stopping_rule", ""),
                    "start_cost": round(info["start_cost"], 3) if "start_cost" in info else ""}
            if decision is None:
                _row.update(status="no feasible decision found", checker="n/a")
            else:
                with open(_path, "w", encoding="utf-8", newline="\n") as _f:
                    json.dump(decision, _f, indent=2)
                with open(_path.parent / "run_info.json", "w", encoding="utf-8", newline="\n") as _f:
                    json.dump(dict(info, computation_time_s=seconds), _f, indent=2)
                report = check_decision(data, decision)
                _m = report["measures"]
                _row.update(status="feasible", checker="feasible" if report["feasible"] else "INFEASIBLE",
                            total_travel_time=round(_m["total_travel_time"], 3), vehicles_used=_m["vehicles_used"],
                            waiting_time=round(_m["waiting_time"], 3), self_crossings=_m["self_crossings"])
            _rows.append(_row)
    RESULTS.mkdir(exist_ok=True)
    _columns = ["instance", "customers", "method", "status", "checker", "total_travel_time", "vehicles_used",
                "waiting_time", "self_crossings", "computation_time_s", "stopping_rule", "start_cost"]
    with open(RESULTS / "comparison.csv", "w", newline="", encoding="utf-8") as _f:
        _writer = csv.DictWriter(_f, lineterminator="\n", fieldnames=_columns)
        _writer.writeheader()
        _writer.writerows(_rows)
    _write_comparison_md(_rows)
    _plot_comparison(_rows)
    for _name in INSTANCES:
        _plot_routes(_name)
    return _rows


def _write_comparison_md(rows):
    _lines = [
        "# Deterministic comparison", "",
        f"- Computer: {machine()}",
        f"- Researched method defaults: seed {researched.DEFAULT_SEED}, {researched.DEFAULT_CHAINS} chains x "
        f"{researched.DEFAULT_ITERATIONS} ruin-and-recreate iterations, safety time cap "
        f"{researched.DEFAULT_TIME_LIMIT:.0f} s ("
        + ("reached on at least one run" if any("time limit" in str(r["stopping_rule"]) for r in rows)
           else "never reached") + ")",
        "- The rule to beat has no settings and no time limit.",
        "- Every measure was recomputed by the independent checker from the written decision.json.",
        "- Self-crossings count pairs of legs of one route that cross on the map (the team's added "
        "constraint; the researched method enforces zero, the rule is implemented exactly as the brief states).",
        "", "| Instance | Customers | Method | Checker | Total travel (min) | Vehicles used | Waiting (min) | "
        "Self-crossings | Computation time (s) |", "| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for _r in rows:
        if _r["status"] != "feasible":
            _lines.append(f"| {_r['instance']} | {_r['customers']} | {_r['method']} | {_r['status']} | - | - | - | - | "
                          f"{_r['computation_time_s']:.3f} |")
        else:
            _lines.append(f"| {_r['instance']} | {_r['customers']} | {_r['method']} | {_r['checker']} | "
                          f"{_r['total_travel_time']:.3f} | {_r['vehicles_used']} | {_r['waiting_time']:.3f} | "
                          f"{_r['self_crossings']} | {_r['computation_time_s']:.3f} |")
    _lines += ["", "## Researched method against the rule to beat", "",
               "| Instance | Rule travel | Researched travel | Saving (min) | Saving (%) | Vehicles rule -> researched |",
               "| --- | ---: | ---: | ---: | ---: | --- |"]
    _by = {(r["instance"], r["method"]): r for r in rows}
    for _name in INSTANCES:
        _a, _b = _by[(_name, "rule")], _by[(_name, "researched")]
        _save = _a["total_travel_time"] - _b["total_travel_time"]
        _lines.append(f"| {_name} | {_a['total_travel_time']:.3f} | {_b['total_travel_time']:.3f} | {_save:.3f} | "
                      f"{100 * _save / _a['total_travel_time']:.1f}% | {_a['vehicles_used']} -> {_b['vehicles_used']} |")
    (RESULTS / "comparison.md").write_text("\n".join(_lines) + "\n", encoding="utf-8", newline="\n")


def _plot_comparison(rows):
    _by = {(r["instance"], r["method"]): r for r in rows}
    _labels = [n.replace("development_", "") + f"\n({_by[(n, 'rule')]['customers']})" for n in INSTANCES]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    for ax, _key, _title in ((axes[0], "total_travel_time", "Total travel time (min), primary measure"),
                             (axes[1], "vehicles_used", "Vehicles used, secondary measure")):
        _style(ax)
        for _j, _method in enumerate(METHODS):
            _x = [i + (_j - 0.5) * 0.38 for i in range(len(INSTANCES))]
            _y = [_by[(n, _method)][_key] for n in INSTANCES]
            ax.bar(_x, _y, width=0.36, color=COLOR[_method], label=METHODS[_method].split(" (")[0],
                   edgecolor="white", linewidth=2)
            for _xi, _yi in zip(_x, _y):
                ax.text(_xi, _yi, f"{_yi:,.0f}" if _key == "total_travel_time" else f"{_yi}",
                        ha="center", va="bottom", fontsize=8, color=INK)
        ax.set_xticks(range(len(INSTANCES)), _labels)
        ax.set_title(_title, fontsize=11, color=INK, loc="left")
    axes[0].legend(frameon=False, fontsize=9)
    fig.text(0.01, 0.01, "Instance (customers). Values recomputed by the independent checker.", fontsize=8, color=MUTED)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(RESULTS / "comparison.png", dpi=160)
    plt.close(fig)


def _plot_routes(name):
    data = load_instance(ROOT / name)
    _loc, _depot = data["locations"], data["depot"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.4))
    for ax, _method in zip(axes, METHODS):
        with open(_decision_path(name, _method), encoding="utf-8") as _f:
            report = check_decision(data, json.load(_f))
        for _route in report["routes"]:
            _stops = [_depot] + _route["visits"] + [_depot]
            _pts = [_loc[s] for s in _stops]
            ax.plot([p[0] for p in _pts], [p[1] for p in _pts], color=COLOR[_method], linewidth=1.6, alpha=0.85)
            if _route["self_crossings"]:
                ax.plot([p[0] for p in _pts], [p[1] for p in _pts], color=CROSSING, linewidth=2.6,
                        linestyle=(0, (4, 2)))
        _cx = [_loc[c][0] for c in data["customers"]]
        _cy = [_loc[c][1] for c in data["customers"]]
        ax.scatter(_cx, _cy, s=22, color="white", edgecolor=INK, linewidth=0.8, zorder=3)
        ax.scatter([_loc[_depot][0]], [_loc[_depot][1]], s=120, marker="s", color=INK, zorder=4)
        _m = report["measures"]
        ax.set_title(f"{METHODS[_method].split(' (')[0]}: {_m['total_travel_time']:.1f} min, "
                     f"{_m['vehicles_used']} vehicles, {_m['self_crossings']} self-crossings",
                     fontsize=10, color=INK, loc="left")
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        for _s in ax.spines.values():
            _s.set_color(GRID)
    fig.suptitle(f"{name}: routes drawn on the plotting coordinates (black square = depot; dashed black = a route "
                 f"that crosses itself)", fontsize=10, color=MUTED, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(RESULTS / f"routes_{name}.png", dpi=150)
    plt.close(fig)


# --- stress test ------------------------------------------------------------------

def _lognormal(rng, cv):
    _sigma = math.sqrt(math.log(1 + cv * cv))
    return rng.lognormvariate(-_sigma * _sigma / 2, _sigma)  # mean exactly 1


def generate_scenarios():
    """Draw and save every scenario before any plan is executed."""
    data = load_instance(ROOT / STRESS_INSTANCE)
    rng = random.Random(STRESS_SEED)
    _folder = RESULTS / "stress" / "scenarios"
    _folder.mkdir(parents=True, exist_ok=True)
    _pairs = sorted(data["travel"])
    _factors = []
    for _s in range(1, SCENARIOS + 1):
        _congestion = _lognormal(rng, CONGESTION_CV)
        _factors.append({"scenario": _s, "congestion_factor": _congestion})
        with open(_folder / f"scenario_{_s:02d}.csv", "w", newline="", encoding="utf-8") as _f:
            _writer = csv.writer(_f, lineterminator="\n")
            _writer.writerow(["from_id", "to_id", "travel_time"])
            for _a, _b in _pairs:
                _base = data["travel"][(_a, _b)]
                _writer.writerow([_a, _b, repr(_base * _congestion * _lognormal(rng, LEG_CV)) if _a != _b else 0.0])
    with open(_folder / "congestion_factors.csv", "w", newline="", encoding="utf-8") as _f:
        _writer = csv.DictWriter(_f, lineterminator="\n", fieldnames=["scenario", "congestion_factor"])
        _writer.writeheader()
        _writer.writerows(_factors)
    print(f"saved {SCENARIOS} scenarios (seed {STRESS_SEED}) to {_folder.relative_to(ROOT)}")


def execute_plan(data, decision, travel):
    """Fixed-plan execution rule from the brief: follow every route in order,
    wait if early, and count each service that starts after its window end and
    each late return as a constraint violation."""
    _total, _late_services, _late_returns, _lateness = 0.0, 0, 0, 0.0
    for _route in decision["routes"]:
        _vehicle = data["vehicles"][_route["vehicle_id"]]
        _time, _here = _vehicle["shift_start"], data["depot"]
        for _c in _route["visits"]:
            _cust = data["customers"][_c]
            _total += travel[(_here, _c)]
            _start = max(_time + travel[(_here, _c)], _cust["window_start"])
            if _start > _cust["window_end"] + 1e-8:
                _late_services += 1
                _lateness += _start - _cust["window_end"]
            _time, _here = _start + _cust["service_time"], _c
        _total += travel[(_here, data["depot"])]
        _return = _time + travel[(_here, data["depot"])]
        if _return > _vehicle["shift_end"] + 1e-8:
            _late_returns += 1
            _lateness += _return - _vehicle["shift_end"]
    return {"total_travel_time": _total, "vehicles_used": len(decision["routes"]), "late_services": _late_services,
            "late_returns": _late_returns, "violations": _late_services + _late_returns, "lateness_min": _lateness}


def _p90(values):
    return statistics.quantiles(values, n=10, method="inclusive")[8]


def stress():
    data = load_instance(ROOT / STRESS_INSTANCE)
    _folder = RESULTS / "stress" / "scenarios"
    if not (_folder / f"scenario_{SCENARIOS:02d}.csv").exists():
        generate_scenarios()
    _plans = {}
    for _method in METHODS:
        _path = _decision_path(STRESS_INSTANCE, _method)
        if not _path.exists():  # the plans come from the deterministic comparison
            decision, _, _ = run_method(data, _method)
            _path.parent.mkdir(parents=True, exist_ok=True)
            with open(_path, "w", encoding="utf-8", newline="\n") as _f:
                json.dump(decision, _f, indent=2)
        with open(_path, encoding="utf-8") as _f:
            _plans[_method] = json.load(_f)
    _rows = []
    for _s in range(1, SCENARIOS + 1):
        with open(_folder / f"scenario_{_s:02d}.csv", newline="", encoding="utf-8") as _f:
            _travel = {(r["from_id"], r["to_id"]): float(r["travel_time"]) for r in csv.DictReader(_f)}
        for _method in METHODS:
            _rows.append(dict(scenario=_s, method=_method, **execute_plan(data, _plans[_method], _travel)))
    with open(RESULTS / "stress" / "stress_results.csv", "w", newline="", encoding="utf-8") as _f:
        _writer = csv.DictWriter(_f, lineterminator="\n", fieldnames=list(_rows[0]))
        _writer.writeheader()
        _writer.writerows(_rows)
    _summary = {}
    for _method in METHODS:
        _mine = [r for r in _rows if r["method"] == _method]
        _travel = [r["total_travel_time"] for r in _mine]
        _vehicles = [r["vehicles_used"] for r in _mine]
        _base = check_decision(data, _plans[_method])["measures"]
        _summary[_method] = {
            "planned_travel": _base["total_travel_time"],
            "travel_mean": statistics.mean(_travel), "travel_p90": _p90(_travel),
            "vehicles_mean": statistics.mean(_vehicles), "vehicles_p90": _p90(_vehicles),
            "scenarios_with_violation": sum(1 for r in _mine if r["violations"] > 0),
            "violations_total": sum(r["violations"] for r in _mine),
            "violations_mean": statistics.mean(r["violations"] for r in _mine),
            "violations_p90": _p90([r["violations"] for r in _mine]),
            "late_services_total": sum(r["late_services"] for r in _mine),
            "late_returns_total": sum(r["late_returns"] for r in _mine),
            "lateness_mean_min": statistics.mean(r["lateness_min"] for r in _mine),
        }
    with open(RESULTS / "stress" / "stress_summary.json", "w", encoding="utf-8", newline="\n") as _f:
        json.dump({"instance": STRESS_INSTANCE, "seed": STRESS_SEED, "scenarios": SCENARIOS,
                   "congestion_cv": CONGESTION_CV, "leg_cv": LEG_CV, "summary": _summary}, _f, indent=2)
    _write_stress_md(_summary)
    _plot_stress(_rows)
    _sensitivity(data, _plans)
    return _summary


SENSITIVITY_MEANS = [1.0, 1.1, 1.2, 1.3]


def _sensitivity(data, plans):
    """Heavier average congestion: the same 30 saved scenarios, every leg scaled
    by a common factor (common random numbers, so only the level changes)."""
    _folder = RESULTS / "stress" / "scenarios"
    _saved = []
    for _s in range(1, SCENARIOS + 1):
        with open(_folder / f"scenario_{_s:02d}.csv", newline="", encoding="utf-8") as _f:
            _saved.append({(r["from_id"], r["to_id"]): float(r["travel_time"]) for r in csv.DictReader(_f)})
    _lines = ["# Sensitivity to heavier congestion", "",
              "Each row rescales every leg of the 30 saved scenarios by the stated mean congestion level and "
              "executes the same two fixed plans by the brief's rule.", "",
              "| Mean congestion | Method | Mean travel (min) | Scenarios with a violation (of 30) | "
              "Violations, total | Late returns, total | Minutes late per scenario, mean |",
              "| ---: | --- | ---: | ---: | ---: | ---: | ---: |"]
    _table = []
    for _level in SENSITIVITY_MEANS:
        for _method in METHODS:
            _runs = [execute_plan(data, plans[_method], {k: v * _level for k, v in _t.items()}) for _t in _saved]
            _row = {"mean_congestion": _level, "method": _method,
                    "travel_mean": statistics.mean(r["total_travel_time"] for r in _runs),
                    "scenarios_with_violation": sum(1 for r in _runs if r["violations"]),
                    "violations_total": sum(r["violations"] for r in _runs),
                    "late_returns_total": sum(r["late_returns"] for r in _runs),
                    "lateness_mean_min": statistics.mean(r["lateness_min"] for r in _runs)}
            _table.append(_row)
            _lines.append(f"| {_level:.1f} | {_method} | {_row['travel_mean']:.1f} | {_row['scenarios_with_violation']} | "
                          f"{_row['violations_total']} | {_row['late_returns_total']} | {_row['lateness_mean_min']:.1f} |")
    (RESULTS / "stress" / "sensitivity.md").write_text("\n".join(_lines) + "\n", encoding="utf-8", newline="\n")
    with open(RESULTS / "stress" / "sensitivity.csv", "w", newline="", encoding="utf-8") as _f:
        _writer = csv.DictWriter(_f, lineterminator="\n", fieldnames=list(_table[0]))
        _writer.writeheader()
        _writer.writerows(_table)


def _write_stress_md(summary):
    _lines = [
        "# Stress test of the fixed plans", "",
        f"- Instance: {STRESS_INSTANCE}; {SCENARIOS} scenarios drawn from seed {STRESS_SEED} and saved to "
        "results/stress/scenarios/ before either plan is executed.",
        f"- Uncertain input: travel time.  Scenario s multiplies every leg by C_s x E_ij, where the day-wide "
        f"congestion factor C_s and each leg's own factor E_ij are independent lognormal draws with mean 1 and "
        f"coefficients of variation {CONGESTION_CV} and {LEG_CV}.",
        "- Execution rule (brief): each planned route is followed in its planned order; a vehicle that arrives "
        "early waits; every service that starts after its window end and every return after the shift end "
        "counts as a constraint violation.  No decision is changed.", "",
        "| Measure | Rule to beat | Researched |", "| --- | ---: | ---: |"]
    _a, _b = summary["rule"], summary["researched"]
    for _label, _key, _fmt in (("Planned total travel (min)", "planned_travel", "{:.3f}"),
                               ("Mean total travel (min)", "travel_mean", "{:.3f}"),
                               ("90th percentile total travel (min)", "travel_p90", "{:.3f}"),
                               ("Mean vehicles used", "vehicles_mean", "{:.1f}"),
                               ("90th percentile vehicles used", "vehicles_p90", "{:.1f}"),
                               ("Scenarios with at least one violation (of 30)", "scenarios_with_violation", "{}"),
                               ("Violations, total over 30 scenarios", "violations_total", "{}"),
                               ("Violations per scenario, mean", "violations_mean", "{:.2f}"),
                               ("Violations per scenario, 90th percentile", "violations_p90", "{:.1f}"),
                               ("Late service starts, total", "late_services_total", "{}"),
                               ("Late returns, total", "late_returns_total", "{}"),
                               ("Minutes late per scenario, mean", "lateness_mean_min", "{:.2f}")):
        _lines.append(f"| {_label} | {_fmt.format(_a[_key])} | {_fmt.format(_b[_key])} |")
    _lines += ["", "The 90th percentile uses Python's statistics.quantiles(n=10, method='inclusive')."]
    (RESULTS / "stress" / "stress_summary.md").write_text("\n".join(_lines) + "\n", encoding="utf-8", newline="\n")


def _plot_stress(rows):
    fig, axes = plt.subplots(3, 1, figsize=(10, 8.4), sharex=True, gridspec_kw={"height_ratios": [3, 1.3, 2]})
    _x = list(range(1, SCENARIOS + 1))
    for _j, _method in enumerate(METHODS):
        _mine = [r for r in rows if r["method"] == _method]
        _label = METHODS[_method].split(" (")[0]
        axes[0].plot(_x, [r["total_travel_time"] for r in _mine], color=COLOR[_method], linewidth=2,
                     marker="o", markersize=5, label=_label)
        axes[1].step(_x, [r["vehicles_used"] for r in _mine], where="mid", color=COLOR[_method], linewidth=2,
                     label=_label)
        axes[2].bar([x + (_j - 0.5) * 0.4 for x in _x], [r["violations"] for r in _mine], width=0.38,
                    color=COLOR[_method], label=_label, edgecolor="white", linewidth=1)
    for ax in axes:
        _style(ax)
    axes[0].set_title("Realized total travel time (min) of each fixed plan", fontsize=11, color=INK, loc="left")
    axes[1].set_title("Vehicles used, secondary measure (fixed plans, so constant)", fontsize=11, color=INK, loc="left")
    axes[1].set_ylim(0, max(r["vehicles_used"] for r in rows) + 3)
    axes[2].set_title("Constraint violations (late service starts + late returns)", fontsize=11, color=INK, loc="left")
    axes[0].legend(frameon=False, fontsize=9)
    axes[2].set_xlabel("Scenario", color=MUTED)
    axes[2].set_xticks(_x)
    for ax in axes[1:]:
        ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
    fig.tight_layout()
    fig.savefig(RESULTS / "stress" / "stress_per_scenario.png", dpi=160)
    plt.close(fig)


def reproduce():
    generate_scenarios()  # scenarios are saved before any method runs
    compare()
    stress()
    print("regenerated results/comparison.*, results/routes_*.png, and results/stress/*")
