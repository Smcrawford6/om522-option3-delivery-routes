"""Automated tests (pixi run test).

Tests 1-3 are the three the project guide requires; the rest guard the
checker, the loader, and the team's no-self-crossing constraint.
"""

import csv
import json
import random
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from vrptw import researched
from vrptw.checker import check_decision, count_self_crossings
from vrptw.core import Instance, route_crosses, to_decision
from vrptw.loader import InputError, load_instance
from vrptw.rule import nearest_feasible_neighbor

ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args):
    return subprocess.run([sys.executable, "-m", "vrptw", *map(str, args)], cwd=ROOT,
                          capture_output=True, text=True)


# --- required test 1: the rule to beat reproduces the worked example ------------

def test_rule_reproduces_worked_example():
    data = load_instance(ROOT / "hand_checkable")
    inst = Instance(data)
    decision = to_decision(nearest_feasible_neighbor(inst), inst)
    expected = json.loads((ROOT / "worked-example" / "solution.json").read_text())
    assert [r["vehicle_id"] for r in decision["routes"]] == [r["vehicle_id"] for r in expected["routes"]]
    for mine, theirs in zip(decision["routes"], expected["routes"]):
        assert mine["visits"] == theirs["visits"]
        assert mine["arrivals"] == pytest.approx(theirs["arrivals"], abs=1e-6)
        assert mine["service_starts"] == pytest.approx(theirs["service_starts"], abs=1e-6)
        assert mine["return_time"] == pytest.approx(theirs["return_time"], abs=1e-6)
    metrics = json.loads((ROOT / "worked-example" / "metrics.json").read_text())
    report = check_decision(data, decision)
    assert report["feasible"]
    assert round(report["measures"]["total_travel_time"], 3) == metrics["total_travel_time"]
    assert report["measures"]["vehicles_used"] == metrics["vehicles_used"]
    assert report["measures"]["waiting_time"] == pytest.approx(metrics["waiting_time"], abs=1e-6)
    assert report["measures"]["customers_served"] == metrics["customers_served"]


# --- required test 2: the edge case gives "no feasible decision found" -----------

@pytest.mark.parametrize("method", ["rule", "researched"])
def test_edge_case_reports_no_feasible_decision(tmp_path, method):
    result = run_cli("solve", ROOT / "edge_case", tmp_path, "--method", method)
    assert result.returncode == 0
    assert "no feasible decision found" in result.stdout
    assert not (tmp_path / "decision.json").exists()


# --- required test 3: a deleted required column is rejected clearly ----------------

def test_missing_column_is_rejected(tmp_path):
    copy = tmp_path / "instance"
    shutil.copytree(ROOT / "hand_checkable", copy)
    with open(copy / "customers.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    with open(copy / "customers.csv", "w", newline="") as f:
        columns = [c for c in rows[0] if c != "window_end"]
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    out = tmp_path / "out"
    result = run_cli("solve", copy, out)
    assert result.returncode != 0
    assert "customers.csv" in result.stderr and "window_end" in result.stderr
    assert not (out / "decision.json").exists()


# --- further checks -----------------------------------------------------------------

@pytest.mark.parametrize("file_name, column, bad", [
    ("customers.csv", "demand", "seven"),            # wrong type
    ("customers.csv", "service_time", "0"),          # duration not positive
    ("vehicles.csv", "capacity", ""),                # empty, not nullable
    ("travel_times.csv", "to_id", "C999"),           # unknown identifier
])
def test_other_input_checks(tmp_path, file_name, column, bad):
    copy = tmp_path / "instance"
    shutil.copytree(ROOT / "hand_checkable", copy)
    with open(copy / file_name, newline="") as f:
        rows = list(csv.DictReader(f))
    rows[0][column] = bad
    with open(copy / file_name, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(InputError, match=f"{file_name}.*{column}"):
        load_instance(copy)


def test_checker_catches_broken_decisions():
    data = load_instance(ROOT / "hand_checkable")
    good = json.loads((ROOT / "worked-example" / "solution.json").read_text())
    dropped = json.loads(json.dumps(good))
    dropped["routes"][0]["visits"].pop()                       # C004 never served
    assert any("C004" in v for v in check_decision(data, dropped)["violations"])
    late = json.loads(json.dumps(good))
    late["routes"][0]["visits"] = ["C002", "C003", "C004"]     # C003 reached after its window
    assert any("C003" in v and "window" in v for v in check_decision(data, late)["violations"])
    heavy = {"routes": [{"vehicle_id": "V01", "visits": ["C001", "C002", "C003", "C004", "C005", "C006"]}]}
    assert any("capacity" in v for v in check_decision(data, heavy)["violations"])
    twice = {"routes": good["routes"] + [{"vehicle_id": "V01", "visits": ["C001"]}]}
    report = check_decision(data, twice)
    assert any("more than one route" in v for v in report["violations"])
    assert any("C001" in v and "2 times" in v for v in report["violations"])


def test_method_and_checker_agree_on_crossings():
    """The method's crossing test and the checker's are written separately."""
    data = load_instance(ROOT / "development_medium")
    inst = Instance(data)
    rng = random.Random(1)
    for _ in range(400):
        route = rng.sample(range(1, inst.n + 1), rng.randint(1, 9))
        stops = [inst.ids[0]] + [inst.ids[c] for c in route] + [inst.ids[0]]
        assert route_crosses(route, inst.xy) == (count_self_crossings(stops, data["locations"]) > 0)


@pytest.mark.parametrize("name", ["hand_checkable", "development_small"])
def test_researched_is_feasible_uncrossed_and_beats_rule(name):
    data = load_instance(ROOT / name)
    inst = Instance(data)
    rule = check_decision(data, to_decision(nearest_feasible_neighbor(inst), inst))
    routes, info = researched.solve(inst, iterations=200, chains=1)
    report = check_decision(data, to_decision(routes, inst))
    assert report["feasible"] and not report["warnings"]
    assert report["measures"]["self_crossings"] == 0
    assert report["measures"]["total_travel_time"] < rule["measures"]["total_travel_time"] - 0.001
    assert info["stopping_rule"] == "iteration count"


def test_researched_is_reproducible():
    inst = Instance(load_instance(ROOT / "development_small"))
    first, _ = researched.solve(inst, iterations=100, chains=2, seed=7)
    second, _ = researched.solve(inst, iterations=100, chains=2, seed=7)
    assert first == second


def test_reordered_rows_give_same_rule_travel(tmp_path):
    """Identifiers are matched by value, never by row position."""
    copy = tmp_path / "instance"
    shutil.copytree(ROOT / "development_small", copy)
    for file_name in ("customers.csv", "travel_times.csv", "vehicles.csv"):
        with open(copy / file_name, newline="") as f:
            reader = csv.DictReader(f)
            columns, rows = reader.fieldnames, list(reader)
        rows.reverse()
        with open(copy / file_name, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
    base = check_decision(load_instance(ROOT / "development_small"),
                          to_decision(nearest_feasible_neighbor(Instance(load_instance(ROOT / "development_small"))),
                                      Instance(load_instance(ROOT / "development_small"))))
    data = load_instance(copy)
    inst = Instance(data)
    moved = check_decision(data, to_decision(nearest_feasible_neighbor(inst), inst))
    assert moved["measures"]["total_travel_time"] == pytest.approx(base["measures"]["total_travel_time"])


def test_solve_command_writes_decision_and_summary(tmp_path):
    result = run_cli("solve", ROOT / "hand_checkable", tmp_path, "--iterations", "50", "--chains", "1")
    assert result.returncode == 0, result.stderr
    decision = json.loads((tmp_path / "decision.json").read_text())
    assert check_decision(load_instance(ROOT / "hand_checkable"), decision)["feasible"]
    assert (tmp_path / "summary.md").exists()
    check = run_cli("check", ROOT / "hand_checkable", tmp_path / "decision.json")
    assert check.returncode == 0 and "FEASIBLE" in check.stdout


def make_proxy(tmp_path, size=60, seed=3):
    """A held-out-sized instance: customers sampled from development_large,
    every identifier renamed, so nothing depends on the supplied files."""
    src = ROOT / "development_large"
    rng = random.Random(seed)
    with open(src / "customers.csv", newline="") as f:
        customers = list(csv.DictReader(f))
    chosen = rng.sample(customers, size)
    rename = {c["customer_id"]: f"STOP-{i:03d}" for i, c in enumerate(chosen)}
    rename["DEPOT"] = "DEPOT"
    out = tmp_path / "proxy"
    out.mkdir()
    shutil.copy(src / "depots.csv", out / "depots.csv")
    with open(src / "vehicles.csv", newline="") as f:
        vehicles = list(csv.DictReader(f))[:24]
    with open(out / "vehicles.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(vehicles[0]))
        writer.writeheader()
        writer.writerows(dict(v, vehicle_id=f"TRUCK{i:02d}") for i, v in enumerate(vehicles))
    with open(out / "customers.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(chosen[0]))
        writer.writeheader()
        writer.writerows(dict(c, customer_id=rename[c["customer_id"]]) for c in chosen)
    with open(src / "travel_times.csv", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["from_id"] in rename and r["to_id"] in rename]
    with open(out / "travel_times.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["from_id", "to_id", "travel_time"])
        writer.writeheader()
        writer.writerows(dict(r, from_id=rename[r["from_id"]], to_id=rename[r["to_id"]]) for r in rows)
    return out


@pytest.mark.parametrize("seed", [2, 3])
def test_researched_never_crosses_on_held_out_sized_proxy(tmp_path, seed):
    """Ruin can shortcut a route into a crossing; the search must reject it."""
    data = load_instance(make_proxy(tmp_path, seed=seed))
    inst = Instance(data)
    routes, info = researched.solve(inst, iterations=300, chains=1)
    report = check_decision(data, to_decision(routes, inst))
    assert report["feasible"] and report["measures"]["self_crossings"] == 0
    assert info["crossing_rule"] == "enforced"
    rule = check_decision(data, to_decision(nearest_feasible_neighbor(inst), inst))
    assert report["measures"]["total_travel_time"] < rule["measures"]["total_travel_time"] - 0.001


@pytest.mark.parametrize("text, accepted", [("7", True), ("7.0", True), ("7.5", False)])
def test_integer_columns_accept_whole_numbers_only(tmp_path, text, accepted):
    copy = tmp_path / "instance"
    shutil.copytree(ROOT / "hand_checkable", copy)
    with open(copy / "customers.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    rows[0]["demand"] = text
    with open(copy / "customers.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    if accepted:
        assert load_instance(copy)["customers"]["C001"]["demand"] == 7
    else:
        with pytest.raises(InputError, match="customers.csv.*demand.*row 2"):
            load_instance(copy)


def test_malformed_input_removes_stale_decision(tmp_path):
    copy = tmp_path / "instance"
    shutil.copytree(ROOT / "hand_checkable", copy)
    (copy / "vehicles.csv").unlink()
    out = tmp_path / "out"
    out.mkdir()
    (out / "decision.json").write_text("{}")
    result = run_cli("solve", copy, out)
    assert result.returncode != 0 and "vehicles.csv" in result.stderr
    assert not (out / "decision.json").exists()
