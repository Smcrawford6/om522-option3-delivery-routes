"""Command line: solve, check, compare, stress, reproduce.

    python -m vrptw solve <input_dir> <output_dir> [--method researched|rule]
    python -m vrptw check <input_dir> <decision.json>
    python -m vrptw compare     # deterministic comparison on the four supplied instances
    python -m vrptw stress      # 30-scenario stress test of both fixed plans
    python -m vrptw reproduce   # scenarios, comparison, stress test, every table and plot

Exit status: 0 for a decision or for "no feasible decision found", 2 for
input that fails a check (no decision.json is written in either failure).
"""

import argparse
import json
import platform
import sys
import time
from pathlib import Path

from . import researched
from .checker import check_decision
from .core import Instance, to_decision
from .loader import InputError, load_instance
from .rule import nearest_feasible_neighbor

NO_DECISION = "no feasible decision found"


def run_method(data, method, iterations=researched.DEFAULT_ITERATIONS, chains=researched.DEFAULT_CHAINS,
               seed=researched.DEFAULT_SEED, time_limit=researched.DEFAULT_TIME_LIMIT, log=None):
    """Solve with one method; returns (decision or None, run information, seconds)."""
    inst = Instance(data)
    _clock = time.perf_counter()
    if method == "rule":
        _routes = nearest_feasible_neighbor(inst)
        _info = {"method": "rule to beat (nearest feasible neighbor)", "stopping_rule": "all vehicles returned",
                 "status": "feasible" if _routes is not None else NO_DECISION}
    else:
        _routes, _info = researched.solve(inst, iterations=iterations, chains=chains, seed=seed,
                                          time_limit=time_limit, log=log)
    _seconds = time.perf_counter() - _clock
    return (to_decision(_routes, inst) if _routes is not None else None), _info, _seconds


def write_summary(out, status, method_info, seconds, report=None):
    _summary = {"status": status, "computation_time_s": seconds, "method": method_info}
    if report is not None:
        _summary["checker"] = {"feasible": report["feasible"], "violations": report["violations"],
                               "warnings": report["warnings"], "measures": report["measures"]}
    with open(out / "summary.json", "w", encoding="utf-8") as _f:
        json.dump(_summary, _f, indent=2)
    _lines = [f"# Run summary", "", f"- Status: {status}", f"- Method: {method_info.get('method')}",
              f"- Stopping rule: {method_info.get('stopping_rule', 'n/a')}",
              f"- Computation time: {seconds:.3f} s"]
    if "crossing_rule" in method_info:
        _lines.append(f"- No-self-crossing rule (team constraint): {method_info['crossing_rule']}")
    if "seed" in method_info:
        _lines.append(f"- Seed: {method_info['seed']} ({method_info['chains']} chains x "
                      f"{method_info['iterations_per_chain']} iterations, safety cap {method_info['time_limit_s']} s)")
    if report is not None:
        _m = report["measures"]
        _lines += [f"- Independent checker: {'feasible' if report['feasible'] else 'INFEASIBLE'}",
                   f"- Total travel time (primary): {_m['total_travel_time']:.3f} min",
                   f"- Vehicles used (secondary): {_m['vehicles_used']}",
                   f"- Waiting time: {_m['waiting_time']:.3f} min",
                   f"- Customers served: {_m['customers_served']}",
                   f"- Self-crossings (team constraint): {_m['self_crossings']}"]
        _lines += [f"- Violation: {v}" for v in report["violations"]]
    (out / "summary.md").write_text("\n".join(_lines) + "\n", encoding="utf-8")


def cmd_solve(args):
    out = Path(args.output_dir)
    (out / "decision.json").unlink(missing_ok=True)  # never leave a stale decision behind
    try:
        data = load_instance(args.input_dir)
    except InputError as error:
        print(f"input error: {error}", file=sys.stderr)
        return 2
    out.mkdir(parents=True, exist_ok=True)
    _log = (lambda message: print(message, flush=True)) if args.verbose else None
    decision, info, seconds = run_method(data, args.method, args.iterations, args.chains, args.seed,
                                         args.time_limit, _log)
    if decision is None:
        print(NO_DECISION)
        write_summary(out, NO_DECISION, info, seconds)
        return 0
    with open(out / "decision.json", "w", encoding="utf-8") as _f:
        json.dump(decision, _f, indent=2)
    report = check_decision(data, decision)
    write_summary(out, "feasible" if report["feasible"] else "infeasible (see checker)", info, seconds, report)
    _m = report["measures"]
    print(f"{info['method']}: total travel {_m['total_travel_time']:.3f} min, "
          f"{_m['vehicles_used']} vehicles, checker {'feasible' if report['feasible'] else 'INFEASIBLE'}, "
          f"{_m['self_crossings']} self-crossings, {seconds:.2f} s")
    print(f"wrote {out / 'decision.json'}")
    return 0


def cmd_check(args):
    try:
        data = load_instance(args.input_dir)
    except InputError as error:
        print(f"input error: {error}", file=sys.stderr)
        return 2
    with open(args.decision, encoding="utf-8") as _f:
        report = check_decision(data, json.load(_f))
    for _route in report["routes"]:
        print(f"{_route['vehicle_id']}: {' -> '.join(_route['visits'])} | load {_route['load']} | "
              f"travel {_route['travel_time']:.3f} | return {_route['return_time']:.3f} | "
              f"self-crossings {_route['self_crossings']}")
    for _key, _value in report["measures"].items():
        print(f"{_key}: {_value:.3f}" if isinstance(_value, float) else f"{_key}: {_value}")
    for _v in report["violations"]:
        print(f"VIOLATION: {_v}")
    for _w in report["warnings"]:
        print(f"warning: {_w}")
    print("FEASIBLE" if report["feasible"] else "INFEASIBLE")
    return 0 if report["feasible"] else 1


def main(argv=None):
    parser = argparse.ArgumentParser(prog="vrptw", description="Option 3 delivery-route decision tool")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("solve", help="solve one instance directory")
    p.add_argument("input_dir")
    p.add_argument("output_dir")
    p.add_argument("--method", choices=["researched", "rule"], default="researched")
    p.add_argument("--iterations", type=int, default=researched.DEFAULT_ITERATIONS)
    p.add_argument("--chains", type=int, default=researched.DEFAULT_CHAINS)
    p.add_argument("--seed", type=int, default=researched.DEFAULT_SEED)
    p.add_argument("--time-limit", type=float, default=researched.DEFAULT_TIME_LIMIT)
    p.add_argument("--verbose", action="store_true")
    p = sub.add_parser("check", help="check a decision.json against an instance")
    p.add_argument("input_dir")
    p.add_argument("decision")
    sub.add_parser("compare", help="deterministic comparison on the four supplied instances")
    sub.add_parser("stress", help="stress test of both fixed plans on development_medium")
    sub.add_parser("reproduce", help="regenerate every submitted table and figure")
    args = parser.parse_args(argv)
    if args.command == "solve":
        return cmd_solve(args)
    if args.command == "check":
        return cmd_check(args)
    from . import experiments
    if args.command == "compare":
        experiments.compare()
    elif args.command == "stress":
        experiments.stress()
    else:
        experiments.reproduce()
    return 0


def machine():
    return f"{platform.system()} {platform.release()}, {platform.processor() or platform.machine()}, " \
           f"Python {platform.python_version()}"
