import marimo

__generated_with = "0.25.1"
app = marimo.App(width="medium", app_title="Live route-planning demo")


@app.cell
def _():
    # Setup: make the project's `vrptw` package importable from this notebook.
    import sys
    import time
    from pathlib import Path

    import marimo as mo
    import matplotlib.pyplot as plt

    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    from vrptw import researched
    from vrptw.checker import check_decision
    from vrptw.cli import run_method
    from vrptw.loader import InputError, load_instance

    CASES = {
        "Hand-checkable (6 customers)": "hand_checkable",
        "Small (15 customers)": "development_small",
        "Medium (45 customers)": "development_medium",
        "Large (120 customers, about 90 s)": "development_large",
        "Edge case (10 customers, impossible)": "edge_case",
    }
    COLORS = {"rule": "#828a8f", "researched": "#9e1b32"}
    NAMES = {"rule": "Rule to beat", "researched": "Researched method"}
    return (
        CASES,
        COLORS,
        InputError,
        NAMES,
        ROOT,
        check_decision,
        load_instance,
        mo,
        plt,
        researched,
        run_method,
        time,
    )


@app.cell
def _(mo):
    mo.md("""
    # Planning delivery routes: live demo
    **OM 522, Option 3** · Sadie Crawford, Zacc Gleason, Annabelle Kemp

    Pick a day's data, pick a method, and press **Run**. Every number below is computed live
    by the project's own code (`vrptw/`), then re-verified by the independent checker.
    """)
    return


@app.cell
def _(CASES, mo, researched):
    case_picker = mo.ui.dropdown(options=CASES, value="Small (15 customers)", label="Case")
    method_picker = mo.ui.radio(
        options={"Researched method": "researched", "Rule to beat": "rule", "Both, side by side": "both"},
        value="Both, side by side", label="Method", inline=True)
    iterations = mo.ui.slider(start=100, stop=researched.DEFAULT_ITERATIONS, step=100,
                              value=researched.DEFAULT_ITERATIONS, show_value=True,
                              label="Ruin-and-recreate iterations per chain (graded default: 2000)")
    run_button = mo.ui.run_button(label="Run", kind="success")
    mo.vstack([mo.hstack([case_picker, method_picker], justify="start", gap=2), iterations, run_button])
    return case_picker, iterations, method_picker, run_button


@app.cell
def _(InputError, ROOT, case_picker, load_instance, mo):
    # Step 1: read the input files and apply the four input checks.
    try:
        data = load_instance(ROOT / case_picker.value)
        load_error = None
    except InputError as error:
        data, load_error = None, str(error)

    if load_error:
        _out = mo.callout(mo.md(f"**input error:** {load_error}"), kind="danger")
    else:
        _rows = [{"customer": c, **{k: v for k, v in info.items()}} for c, info in sorted(data["customers"].items())]
        _vehicles = [{"vehicle": v, **info} for v, info in sorted(data["vehicles"].items())]
        _out = mo.vstack([
            mo.md(f"## 1. The day's input: `{case_picker.value}/`"),
            mo.md(f"{len(data['customers'])} customers, {len(data['vehicles'])} trucks available, "
                  f"depot `{data['depot']}`. All four input checks passed."),
            mo.ui.tabs({"Customers": mo.ui.table(_rows, selection=None, page_size=10),
                        "Trucks": mo.ui.table(_vehicles, selection=None, page_size=10)}),
        ])
    _out
    return (data,)


@app.cell
def _(data, iterations, method_picker, mo, run_button, run_method, time):
    # Step 2: run the chosen method(s). Nothing runs until Run is pressed.
    mo.stop(not run_button.value, mo.md("## 2. Run\nPress **Run** above to plan this day."))
    mo.stop(data is None, mo.md("Fix the input error first."))

    _methods = ["rule", "researched"] if method_picker.value == "both" else [method_picker.value]
    results = {}
    for _m in _methods:
        with mo.status.spinner(title=f"Running the {'rule to beat' if _m == 'rule' else 'researched method'} ..."):
            _clock = time.perf_counter()
            _decision, _info, _seconds = run_method(data, _m, iterations=iterations.value)
            results[_m] = {"decision": _decision, "info": _info, "seconds": time.perf_counter() - _clock}
    mo.md("## 2. Run\nDone. " + " · ".join(
        f"{'Rule to beat' if m == 'rule' else 'Researched'}: {r['seconds']:.2f} s" for m, r in results.items()))
    return (results,)


@app.cell
def _(NAMES, check_decision, data, mo, results):
    # Step 3: the independent checker recomputes everything from the visit lists.
    reports = {}
    _cards = []
    for _m, _r in results.items():
        if _r["decision"] is None:
            _cap = max(v["capacity"] for v in data["vehicles"].values())
            _big = [f"{c} needs {v['demand']}" for c, v in data["customers"].items() if v["demand"] > _cap]
            _cards.append(mo.callout(mo.md(
                f"**{NAMES[_m]}: no feasible decision found.** "
                + (f"Reason: {', '.join(_big)}, but the largest truck holds {_cap}." if _big else "")),
                kind="warn"))
            continue
        _rep = check_decision(data, _r["decision"])
        reports[_m] = _rep
        _ms = _rep["measures"]
        _cards.append(mo.vstack([
            mo.md(f"### {NAMES[_m]}"),
            mo.hstack([
                mo.stat(f"{_ms['total_travel_time']:,.1f}", label="Total travel (min)"),
                mo.stat(str(_ms["vehicles_used"]), label="Trucks used"),
                mo.stat(f"{_ms['waiting_time']:,.1f}", label="Waiting (min)"),
                mo.stat(str(_ms["self_crossings"]), label="Self-crossings"),
            ], justify="start"),
            mo.callout(mo.md("**Checker: FEASIBLE**" if _rep["feasible"] else
                             "**Checker: INFEASIBLE**<br>" + "<br>".join(_rep["violations"])),
                       kind="success" if _rep["feasible"] else "danger"),
        ]))
    _saving = ""
    if len(reports) == 2:
        _a = reports["rule"]["measures"]["total_travel_time"]
        _b = reports["researched"]["measures"]["total_travel_time"]
        _saving = mo.md(f"**The researched method saves {_a - _b:,.1f} minutes of driving "
                        f"({100 * (_a - _b) / _a:.1f}%).**")
    mo.vstack([mo.md("## 3. Results, re-verified by the independent checker"),
               mo.hstack(_cards, widths="equal") if len(_cards) > 1 else _cards[0]] + ([_saving] if _saving else []))
    return (reports,)


@app.cell
def _(COLORS, NAMES, data, mo, plt, reports):
    # Step 4: draw every truck's route on the map.
    mo.stop(not reports)
    _fig, _axes = plt.subplots(1, len(reports), figsize=(6 * len(reports), 6), squeeze=False)
    _loc, _depot = data["locations"], data["depot"]
    for _ax, (_m, _rep) in zip(_axes[0], reports.items()):
        for _route in _rep["routes"]:
            _pts = [_loc[s] for s in [_depot] + _route["visits"] + [_depot]]
            _ax.plot([p[0] for p in _pts], [p[1] for p in _pts], color=COLORS[_m], linewidth=1.6)
            if _route["self_crossings"]:
                _ax.plot([p[0] for p in _pts], [p[1] for p in _pts], color="black", linewidth=2.4, linestyle="--")
        _ax.scatter([_loc[c][0] for c in data["customers"]], [_loc[c][1] for c in data["customers"]],
                    s=26, color="white", edgecolor="black", zorder=3)
        _ax.scatter(*_loc[_depot], s=130, marker="s", color="black", zorder=4)
        _ms = _rep["measures"]
        _ax.set_title(f"{NAMES[_m]}: {_ms['total_travel_time']:,.1f} min, {_ms['vehicles_used']} trucks",
                      loc="left", fontsize=11)
        _ax.set_aspect("equal")
        _ax.set_xticks([])
        _ax.set_yticks([])
    _fig.tight_layout()
    mo.vstack([mo.md("## 4. Routes on the map\nBlack square = depot. A dashed black line = a route that crosses itself."),
               _fig])
    return


@app.cell
def _(NAMES, mo, reports):
    # Step 5: the plan a dispatcher would hand to the drivers.
    mo.stop(not reports)
    _tabs = {}
    for _m, _rep in reports.items():
        _tabs[NAMES[_m]] = mo.ui.table([{
            "truck": r["vehicle_id"], "stops in order": " -> ".join(r["visits"]), "load": r["load"],
            "driving (min)": round(r["travel_time"], 1), "waiting (min)": round(r["waiting_time"], 1),
            "back at depot (min)": round(r["return_time"], 1)} for r in _rep["routes"]], selection=None)
    mo.vstack([mo.md("## 5. The plan for each driver"), mo.ui.tabs(_tabs)])
    return


@app.cell
def _(mo, results):
    # Step 6 (optional): how the search got there.
    mo.stop("researched" not in results or results["researched"]["decision"] is None)
    _info = results["researched"]["info"]
    _starts = [s for s in _info["starts"] if "constructed" in s]
    _chains = _info.get("chain_results", [])
    mo.accordion({"How the researched search got there (run details)": mo.vstack([
        mo.md(f"- Crossing rule: **{_info['crossing_rule']}**\n"
              f"- Best Solomon I1 start: **{min(s['constructed'] for s in _starts):,.1f}** min, "
              f"after local search: **{_info['start_cost']:,.1f}** min\n"
              f"- After ruin and recreate: **{_info['best_cost']:,.1f}** min "
              f"(seed {_info['seed']}, {_info['chains']} chains x {_info['iterations_per_chain']} iterations, "
              f"stopped by: {_info['stopping_rule']})"),
        mo.ui.table([{"chain": c["chain"], "best (min)": round(c["best_cost"], 3), "found at iteration": c["best_iteration"],
                      "candidates rejected as infeasible": c["rejected_infeasible"]} for c in _chains], selection=None),
    ])})
    return


@app.cell
def _(ROOT, mo):
    # Step 7: the code itself, read straight from the project files.
    def _show(path):
        return mo.md(f"```python\n{(ROOT / path).read_text(encoding='utf-8')}\n```")

    mo.vstack([
        mo.md("## 6. The code that just ran"),
        mo.accordion({
            "vrptw/rule.py: the rule to beat (nearest feasible neighbor)": _show("vrptw/rule.py"),
            "vrptw/researched.py: Solomon I1 + local search + ruin and recreate": _show("vrptw/researched.py"),
            "vrptw/checker.py: the independent checker": _show("vrptw/checker.py"),
        }),
    ])
    return


if __name__ == "__main__":
    app.run()
